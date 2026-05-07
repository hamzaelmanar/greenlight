"""
load_to_duckdb.py
Usage: python ingestion/load_to_duckdb.py
Reads persona/hamza.md and all offers/*_skills.json,
loads them into DuckDB as raw tables for dbt to transform.
"""

import json
import re
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "greenlight.duckdb"
PERSONA_PATH = Path(__file__).parent.parent / "persona" / "hamza.md"
OFFERS_DIR = Path(__file__).parent.parent / "offers"


def parse_persona(md_text: str) -> list[dict]:
    """Parse the Skills section of the persona .md file."""
    rows = []
    in_skills = False
    for line in md_text.splitlines():
        if line.strip() == "## Skills":
            in_skills = True
            continue
        if in_skills and line.startswith("## "):
            break
        if in_skills and line.startswith("#"):
            continue  # comment/header line
        if in_skills and "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                skill, proficiency, in_prod = parts[0], parts[1], parts[2]
                try:
                    rows.append({
                        "skill": skill.lower(),
                        "proficiency": int(proficiency),
                        "in_production": in_prod.lower() == "yes",
                    })
                except ValueError:
                    pass
    return rows


def load(con: duckdb.DuckDBPyConnection, persona_path: Path | None = None):
    # --- persona_skills ---
    md_text = (persona_path or PERSONA_PATH).read_text(encoding="utf-8")
    persona_rows = parse_persona(md_text)

    con.execute("DROP TABLE IF EXISTS raw_persona_skills")
    con.execute("""
        CREATE TABLE raw_persona_skills (
            skill VARCHAR,
            proficiency INTEGER,
            in_production BOOLEAN
        )
    """)
    con.executemany(
        "INSERT INTO raw_persona_skills VALUES (?, ?, ?)",
        [(r["skill"], r["proficiency"], r["in_production"]) for r in persona_rows],
    )
    print(f"Loaded {len(persona_rows)} persona skills")

    # --- offer_skills ---
    skill_files = list(OFFERS_DIR.glob("*_skills.json"))
    if not skill_files:
        print("No offer skill files found in offers/. Run fetch_offer.py + extract_skills.py first.")
        return

    con.execute("DROP TABLE IF EXISTS raw_offer_skills")
    con.execute("""
        CREATE TABLE raw_offer_skills (
            offer_id VARCHAR,
            skill VARCHAR,
            mention_count INTEGER
        )
    """)

    total = 0
    for f in skill_files:
        offer_id = f.stem.replace("_skills", "")
        counts: dict = json.loads(f.read_text(encoding="utf-8"))
        rows = [(offer_id, skill, count) for skill, count in counts.items()]
        if not rows:
            print(f"  {offer_id}: no skills extracted, skipping")
            continue
        con.executemany("INSERT INTO raw_offer_skills VALUES (?, ?, ?)", rows)
        total += len(rows)
        print(f"  {offer_id}: {len(rows)} skills")

    print(f"Loaded {total} offer skill rows from {len(skill_files)} offer(s)")


if __name__ == "__main__":
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    load(con)
    con.close()
    print(f"\nDuckDB → {DB_PATH}")
