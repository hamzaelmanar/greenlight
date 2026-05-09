"""
load_to_duckdb.py
Reads lead-gen's jobs.csv, applies filters, and loads raw_offer_skills into DuckDB.
Also ensures the run_log table exists for run history.

Usage:
    python ingestion/load_to_duckdb.py

Filters are passed as keyword arguments to load():
    mission_types : list[str] | None  — e.g. ["consulting", "pipeline"]
    cities        : list[str] | None  — e.g. ["Paris", "Lille"]
    sources       : list[str] | None  — e.g. ["wttj", "linkedin"]
    max_seniority : int               — 0=in range, 1=stretch, 2=all (default 1)
    min_score     : int               — minimum relevance_score (default 6)

LEAD_GEN_PATH is read from .env (e.g. LEAD_GEN_PATH=../lead-gen).
"""

import ast
import csv
import hashlib
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "data" / "greenlight.duckdb"

def _lead_gen_path() -> Path:
    raw = os.getenv("LEAD_GEN_PATH", "../lead-gen")
    p = Path(raw)
    if not p.is_absolute():
        p = (Path(__file__).parent.parent / p).resolve()
    return p


def _parse_list_field(value: str) -> list[str]:
    """Parse a JSON-encoded list stored as a CSV string field."""
    if not value or value.strip() in ("", "[]"):
        return []
    try:
        result = ast.literal_eval(value)
        return [str(x).lower().strip() for x in result] if isinstance(result, list) else []
    except Exception:
        return []


def load(
    con: duckdb.DuckDBPyConnection,
    mission_types: list[str] | None = None,
    cities: list[str] | None = None,
    sources: list[str] | None = None,
    max_seniority: int = 1,
    min_score: int = 6,
) -> int:
    """
    Load filtered jobs from lead-gen CSV into raw_offer_skills.
    Returns the number of matched offers.
    """
    csv_path = _lead_gen_path() / "data" / "jobs.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"lead-gen jobs.csv not found at {csv_path}")

    # Normalise filter sets to lowercase for comparison
    mission_filter = {m.lower() for m in mission_types} if mission_types else None
    city_filter    = {c.lower() for c in cities} if cities else None
    source_filter  = {s.lower() for s in sources} if sources else None

    rows: list[tuple[str, str, int]] = []  # (offer_id, skill, mention_count)
    matched_offers: set[str] = set()

    with open(csv_path, encoding="utf-8") as f:
        for job in csv.DictReader(f):
            # --- Score filter ---
            try:
                score = int(job.get("relevance_score") or 0)
            except ValueError:
                score = 0
            if score < min_score:
                continue

            # --- Seniority filter ---
            try:
                seniority = int(job.get("seniority_fit") or 0)
            except ValueError:
                seniority = 0
            if seniority > max_seniority:
                continue

            # --- Source filter ---
            if source_filter:
                job_source = (job.get("source") or "").lower().strip()
                if job_source not in source_filter:
                    continue

            # --- City filter ---
            if city_filter:
                job_location = (job.get("location") or "").lower()
                if not any(c in job_location for c in city_filter):
                    continue

            # --- Mission type filter ---
            if mission_filter:
                job_missions = set(_parse_list_field(job.get("mission_types", "")))
                if not job_missions & mission_filter:
                    continue

            # --- Unpack missing_skills → gap signal ---
            missing = _parse_list_field(job.get("missing_skills", ""))
            if not missing:
                continue

            offer_id = hashlib.md5((job.get("url") or job.get("id", "")).encode()).hexdigest()[:10]
            matched_offers.add(offer_id)
            for skill in missing:
                if skill:
                    rows.append((offer_id, skill, 1))

    # Write to DuckDB
    con.execute("DROP TABLE IF EXISTS raw_offer_skills")
    con.execute("""
        CREATE TABLE raw_offer_skills (
            offer_id      VARCHAR,
            skill         VARCHAR,
            mention_count INTEGER
        )
    """)
    if rows:
        con.executemany("INSERT INTO raw_offer_skills VALUES (?, ?, ?)", rows)

    # Ensure run_log table exists
    con.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            run_id       VARCHAR,
            run_at       TIMESTAMP,
            filters      VARCHAR,
            offer_count  INTEGER,
            top_gaps     VARCHAR,
            hook         VARCHAR,
            context_text VARCHAR,
            project_spec VARCHAR
        )
    """)

    n = len(matched_offers)
    print(f"Loaded {len(rows)} skill rows from {n} matched offer(s)")
    return n


if __name__ == "__main__":
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    n = load(con)
    con.close()
    print(f"Done — {n} offers → {DB_PATH}")
