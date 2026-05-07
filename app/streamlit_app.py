"""
app/streamlit_app.py — Greenlight MVP
Run: streamlit run app/streamlit_app.py   (from project root)
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import duckdb
import streamlit as st

from ingestion.extract_skills import extract
from ingestion.fetch_offer import fetch, save
from ingestion.load_to_duckdb import load
from scoring.gap_score import get_top_gaps
from scoring.llm_hook import generate

DB_PATH = ROOT / "data" / "greenlight.duckdb"
OFFERS_DIR = ROOT / "offers"
PERSONA_DIR = ROOT / "persona"
VENV_DBT = ROOT / ".venv" / "Scripts" / "dbt"


def parse_urls(text: str) -> list[str]:
    urls = []
    for line in text.splitlines():
        line = line.strip().lstrip("- ").strip()
        if line.startswith("http"):
            urls.append(line)
    return urls


def parse_target_roles(md_text: str) -> list[str]:
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Target roles" and i + 1 < len(lines):
            return [r.strip() for r in lines[i + 1].split(",") if r.strip()]
    return ["Analytics Engineer", "Data Engineer"]


def run_pipeline(persona_path: Path, urls: list[str], mode: str) -> dict:
    # 1. Fetch + extract offer skills
    for url in urls:
        text = fetch(url)
        path = save(url, text)
        counts = extract(path.read_text(encoding="utf-8"))
        out = path.with_name(path.stem + "_skills.json")
        out.write_text(json.dumps(counts, indent=2), encoding="utf-8")

    # 2. Load into DuckDB
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    load(con, persona_path=persona_path)
    con.close()

    # 3. dbt run
    result = subprocess.run(
        [str(VENV_DBT), "run", "--profiles-dir", "."],
        cwd=ROOT / "transform",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt run failed:\n{result.stdout}\n{result.stderr}")

    # 4. Score + recommend
    gaps = get_top_gaps(10)
    target_roles = parse_target_roles(persona_path.read_text(encoding="utf-8"))
    rec = generate(gaps, target_roles, mode=mode)
    return {"gaps": gaps, "rec": rec}


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Greenlight", page_icon="🟢", layout="wide")

# ── Sidebar — inputs ─────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🟢 Greenlight")
    st.caption("Portfolio gap advisor")
    st.divider()

    st.subheader("1. Persona")
    uploaded_persona = st.file_uploader(
        "Upload your persona `.md` file",
        type=["md"],
        help="Should have a `## Skills` section with skill | level | in_prod rows.",
    )
    if uploaded_persona is None:
        default_persona = PERSONA_DIR / "hamza.md"
        if default_persona.exists():
            st.caption(f"Using default: `persona/hamza.md`")
            persona_path = default_persona
        else:
            st.warning("No persona file found. Upload one to continue.")
            persona_path = None
    else:
        PERSONA_DIR.mkdir(exist_ok=True)
        persona_path = PERSONA_DIR / "uploaded.md"
        persona_path.write_bytes(uploaded_persona.getvalue())
        st.caption(f"Using uploaded: `{uploaded_persona.name}`")

    st.subheader("2. Job offers")
    url_input = st.text_area(
        "Paste URLs (one per line, or paste your `offers.md` content)",
        height=200,
        placeholder="https://www.welcometothejungle.com/fr/companies/...\nhttps://...",
    )

    use_cached = st.checkbox(
        "Skip re-fetching (use already-fetched offers)",
        value=True,
        help="Check this if you already ran the pipeline — avoids redundant HTTP requests.",
    )

    st.subheader("3. Recommendation mode")
    mode = st.radio(
        "Engine",
        options=["llm", "fallback"],
        captions=["Mistral AI (requires API key)", "Template, no API call"],
        index=0,
    )

    st.divider()
    run_btn = st.button("Run analysis", type="primary", use_container_width=True)

# ── Main — results ────────────────────────────────────────────────────────────

st.header("Results")

if not run_btn:
    st.info(
        "Configure your persona and job offers in the sidebar, then click **Run analysis**.",
        icon="👈",
    )
    st.stop()

if persona_path is None:
    st.error("No persona file available. Upload one in the sidebar.")
    st.stop()

urls = parse_urls(url_input)

if not urls and not use_cached:
    st.error("No URLs found. Paste at least one job offer URL in the sidebar.")
    st.stop()

if not urls and use_cached:
    existing = list(OFFERS_DIR.glob("*_skills.json"))
    if not existing:
        st.error("No cached offers found and no URLs provided. Paste URLs and uncheck 'Skip re-fetching'.")
        st.stop()
    urls = []  # pipeline will use what's already in offers/

with st.status("Running pipeline…", expanded=True) as status:
    try:
        if urls:
            st.write(f"Fetching {len(urls)} offer(s)…")
        else:
            st.write("Using cached offer files…")

        if use_cached and not urls:
            # Skip fetch/extract — jump straight to load + dbt + score
            DB_PATH.parent.mkdir(exist_ok=True)
            con = duckdb.connect(str(DB_PATH))
            load(con, persona_path=persona_path)
            con.close()

            st.write("Running dbt transformations…")
            dbt_result = subprocess.run(
                [str(VENV_DBT), "run", "--profiles-dir", "."],
                cwd=ROOT / "transform",
                capture_output=True,
                text=True,
            )
            if dbt_result.returncode != 0:
                raise RuntimeError(f"dbt run failed:\n{dbt_result.stdout}\n{dbt_result.stderr}")

            st.write(f"Scoring gaps ({mode} mode)…")
            gaps = get_top_gaps(10)
            target_roles = parse_target_roles(persona_path.read_text(encoding="utf-8"))
            rec = generate(gaps, target_roles, mode=mode)
            data = {"gaps": gaps, "rec": rec}
        else:
            st.write("Running full pipeline…")
            data = run_pipeline(persona_path, urls, mode)

        status.update(label="Done", state="complete", expanded=False)

    except Exception as exc:
        status.update(label="Pipeline failed", state="error", expanded=True)
        st.exception(exc)
        st.stop()

gaps = data["gaps"]
rec = data["rec"]

if not gaps:
    st.warning("No skill gaps found. Try adding more job offers.")
    st.stop()

# ── Gap table ─────────────────────────────────────────────────────────────────

st.subheader("Skill gap breakdown")

import pandas as pd

df = pd.DataFrame(rec["top_gaps"])
df = df.rename(columns={
    "skill": "Skill",
    "offer_count": "Offer count",
    "gap_score": "Gap score",
    "proficiency": "Your level",
})
df["Gap score"] = df["Gap score"].round(1)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Gap score": st.column_config.ProgressColumn(
            "Gap score",
            min_value=0,
            max_value=float(df["Gap score"].max()) if not df.empty else 10,
            format="%.1f",
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
