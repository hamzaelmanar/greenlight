"""
app/streamlit_app.py — Greenlight v2
Run: streamlit run app/streamlit_app.py   (from project root)

Reads from lead-gen's jobs.csv (path via LEAD_GEN_PATH in .env).
Filters by mission type, city, source, seniority, and minimum relevance score.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import duckdb
import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from ingestion.load_to_duckdb import load, _lead_gen_path
from scoring.gap_score import get_top_gaps
from scoring.llm_hook import generate

DB_PATH = ROOT / "data" / "greenlight.duckdb"

MISSION_OPTIONS = [
    "consulting", "pipeline", "transformation",
    "analytics_engineering", "data_platform", "cloud_migration",
]
CITY_OPTIONS = ["Paris", "Lille", "Nantes", "Lyon", "Malaga", "remote"]
SOURCE_OPTIONS = ["wttj", "linkedin", "apec"]
SENIORITY_LABELS = {0: "In range (0–3y)", 1: "Stretch (≤5y)", 2: "All"}


def _load_persona_prose() -> str | None:
    persona_path = _lead_gen_path() / "backend" / "persona.md"
    if persona_path.exists():
        return persona_path.read_text(encoding="utf-8")
    return None


def _build_filter_ctx(missions, cities, sources, max_seniority, min_score, offer_count) -> str:
    parts = [f"{offer_count} offer{'s' if offer_count != 1 else ''}"]
    if missions:
        parts.append(" · ".join(missions))
    if cities:
        parts.append(" · ".join(cities))
    if sources:
        parts.append(" · ".join(sources))
    parts.append(SENIORITY_LABELS[max_seniority])
    parts.append(f"score ≥ {min_score}")
    return " · ".join(parts)


def _build_cohort_name(missions: list, cities: list, sources: list) -> str:
    city_part = "-".join(c[:2].upper() for c in cities) if cities else "all"
    source_part = "+".join(sources) if sources else "all"
    consulting_part = "c" if "consulting" in missions else "nc"
    return f"{city_part}_{source_part}_{consulting_part}"


def _log_run(con, filters: dict, offer_count: int, gaps: list, rec: dict):
    con.execute(
        """INSERT INTO run_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            datetime.now(timezone.utc),
            json.dumps(filters),
            offer_count,
            json.dumps(gaps[:5]),
            rec.get("hook", ""),
            rec.get("context", ""),
            rec.get("project_spec", ""),
        ),
    )


def _read_run_log() -> list[dict]:
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        rows = con.execute(
            "SELECT run_id, run_at, filters, offer_count, hook FROM run_log ORDER BY run_at DESC LIMIT 10"
        ).fetchall()
        con.close()
        return [
            {"run_id": r[0], "run_at": r[1], "filters": r[2], "offer_count": r[3], "hook": r[4]}
            for r in rows
        ]
    except Exception:
        return []


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Greenlight", page_icon="🟢", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🟢 Greenlight")
    st.caption("Portfolio gap advisor — powered by lead-gen")
    st.divider()

    st.subheader("Filters")

    missions = st.multiselect(
        "Mission type",
        options=MISSION_OPTIONS,
        default=[],
        help="Leave empty to include all mission types.",
    )

    cities = st.multiselect(
        "City",
        options=CITY_OPTIONS,
        default=[],
        help="Matches against the location field. Leave empty for all cities.",
    )

    sources = st.multiselect(
        "Source",
        options=SOURCE_OPTIONS,
        default=[],
        help="Leave empty to include all sources.",
    )

    max_seniority = st.radio(
        "Seniority cap",
        options=[0, 1, 2],
        format_func=lambda x: SENIORITY_LABELS[x],
        index=1,
        help="0 = clearly in range (0–3y). 1 = stretch (3–5y). 2 = include all.",
    )

    min_score = st.slider(
        "Minimum relevance score",
        min_value=0, max_value=10, value=6,
        help="Only offers scored ≥ this value by lead-gen are included.",
    )

    st.divider()
    st.subheader("Recommendation mode")
    mode = st.radio(
        "Engine",
        options=["llm", "fallback"],
        captions=["Mistral AI (requires API key)", "Template, no API call"],
        index=0,
    )

    st.divider()
    run_btn = st.button("Run analysis", type="primary", use_container_width=True)

    cohort_name = _build_cohort_name(missions, cities, sources)
    st.caption(f"Cohort: `{cohort_name}`")

    # Previous runs
    history = _read_run_log()
    if history:
        st.divider()
        with st.expander(f"Previous runs ({len(history)})"):
            for h in history:
                try:
                    f = json.loads(h["filters"])
                except Exception:
                    f = {}
                st.caption(str(h["run_at"])[:16])
                st.markdown(f"**{h['offer_count']} offers** — {h['hook'][:80]}…" if h["hook"] else f"**{h['offer_count']} offers**")
                st.markdown("---")

# ── Main ──────────────────────────────────────────────────────────────────────

st.header("Results")

if not run_btn:
    st.info("Set your filters in the sidebar and click **Run analysis**.", icon="👈")
    st.stop()

with st.status("Running pipeline…", expanded=True) as status:
    try:
        st.write("Loading offers from lead-gen…")
        DB_PATH.parent.mkdir(exist_ok=True)
        con = duckdb.connect(str(DB_PATH))
        offer_count = load(
            con,
            mission_types=missions or None,
            cities=cities or None,
            sources=sources or None,
            max_seniority=max_seniority,
            min_score=min_score,
        )

        if offer_count == 0:
            con.close()
            status.update(label="No offers matched", state="error", expanded=True)
            st.error("No offers matched your filters. Try relaxing the criteria.")
            st.stop()

        # Close write connection before reading (DuckDB: one writer at a time)
        con.close()

        st.write(f"Scoring gaps ({mode} mode)…")
        gaps = get_top_gaps(10)

        filters = {
            "missions": missions, "cities": cities, "sources": sources,
            "max_seniority": max_seniority, "min_score": min_score,
            "cohort": cohort_name,
        }
        filter_ctx = _build_filter_ctx(missions, cities, sources, max_seniority, min_score, offer_count)
        persona_prose = _load_persona_prose()

        rec = generate(gaps, filter_ctx=filter_ctx, persona_prose=persona_prose, mode=mode)

        # Reopen for logging only
        con = duckdb.connect(str(DB_PATH))
        _log_run(con, filters, offer_count, gaps, rec)
        con.close()

        status.update(label="Done", state="complete", expanded=False)

    except Exception as exc:
        status.update(label="Pipeline failed", state="error", expanded=True)
        st.exception(exc)
        st.stop()

if not gaps:
    st.warning("No skill gaps found in the filtered offers.")
    st.stop()

# ── Filter context badge ──────────────────────────────────────────────────────

st.caption(f"Analysis scope: **{filter_ctx}** — cohort `{cohort_name}`")

# ── Gap table ─────────────────────────────────────────────────────────────────

st.subheader("Skill gap breakdown")

import pandas as pd

df = pd.DataFrame(rec["top_gaps"])
df = df.rename(columns={
    "skill": "Skill",
    "offer_count": "Offers missing you",
    "gap_score": "Gap score",
})
df["Gap score"] = df["Gap score"].apply(lambda x: round(float(x), 1))

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Gap score": st.column_config.ProgressColumn(
            "Gap score",
            min_value=0,
            max_value=float(df["Gap score"].max()) if not df.empty else 10,
            format="%.0f",
        ),
    },
)

# ── Recommendation card ───────────────────────────────────────────────────────

st.subheader("Recommendation")

st.markdown(
    f"""
<div style="
    background: #0e1117;
    border: 1px solid #21262d;
    border-left: 4px solid #22c55e;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
">
<p style="font-size: 1.15rem; font-weight: 600; color: #f0f6fc; margin: 0 0 0.75rem 0;">
    {rec['hook']}
</p>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Market context**")
    st.markdown(rec["context"] or "_No context generated._")

with col2:
    st.markdown("**Project spec**")
    st.markdown(rec["project_spec"] or "_No project spec generated._")
