"""
run.py — Greenlight end-to-end pipeline
Usage:
    python run.py "https://url1" "https://url2" ...
    python run.py offers.md        # one URL per line in a .md file

Steps:
    1. Fetch each URL → offers/<hash>.txt
    2. Extract skills → offers/<hash>_skills.json
    3. Load persona + all offer skills into DuckDB
    4. Run dbt (staging + marts)
    5. Print top skill gaps
"""

import sys
import subprocess
from pathlib import Path

from ingestion.fetch_offer import fetch, save, slug
from ingestion.extract_skills import extract
from ingestion.load_to_duckdb import load
from scoring.gap_score import get_top_gaps
from scoring.llm_hook import generate
import duckdb
import json

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "greenlight.duckdb"
OFFERS_DIR = ROOT / "offers"


def step_fetch(urls: list[str]) -> list[Path]:
    print("\n── Step 1: Fetch offers ──────────────────────────")
    txt_paths = []
    for url in urls:
        print(f"  Fetching: {url}")
        text = fetch(url)
        path = save(url, text)
        print(f"  Saved {len(text):,} chars → {path.name}")
        txt_paths.append(path)
    return txt_paths


def step_extract(txt_paths: list[Path]):
    print("\n── Step 2: Extract skills ────────────────────────")
    for path in txt_paths:
        text = path.read_text(encoding="utf-8")
        counts = extract(text)
        out = path.with_name(path.stem + "_skills.json")
        out.write_text(json.dumps(counts, indent=2), encoding="utf-8")
        print(f"  {path.name} → {len(counts)} skills found")


def step_load():
    print("\n── Step 3: Load into DuckDB ──────────────────────")
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    load(con)
    con.close()


def step_dbt():
    print("\n── Step 4: dbt run ───────────────────────────────")
    result = subprocess.run(
        [str(ROOT / ".venv" / "Scripts" / "dbt"), "run", "--profiles-dir", "."],
        cwd=ROOT / "transform",
    )
    if result.returncode != 0:
        print("  dbt run failed — check output above.")
        sys.exit(result.returncode)


def step_score():
    print("\n── Step 5: Top skill gaps ────────────────────────")
    gaps = get_top_gaps(10)
    if not gaps:
        print("  No gaps found — do you have offer data loaded?")
        return
    print(f"\n  {'Skill':<20} {'Offers':>8} {'Gap score':>12} {'Your level':<12}")
    print("  " + "-" * 56)
    for g in gaps:
        print(f"  {g['skill']:<20} {g['offer_count']:>8} {g['gap_score']:>12} {g['proficiency']:<12}")
    return gaps


def step_recommend(gaps: list[dict]):
    print("\n── Step 6: Recommendation ────────────────────────")
    persona_path = ROOT / "persona" / "hamza.md"
    target_roles = ["Analytics Engineer", "Data Engineer"]
    if persona_path.exists():
        lines = persona_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip() == "## Target roles" and i + 1 < len(lines):
                target_roles = [r.strip() for r in lines[i + 1].split(",") if r.strip()]
                break

    result = generate(gaps, target_roles, mode="fallback")
    print(f"\n  {result['hook']}")
    if result["context"]:
        print()
        for line in result["context"].splitlines():
            print(f"  {line}")
    if result["project_spec"]:
        print()
        for line in result["project_spec"].splitlines():
            print(f"  {line}")


def resolve_urls(args: list[str]) -> list[str]:
    """Accept a .md file path or bare URLs as arguments."""
    if len(args) == 1 and args[0].endswith(".md"):
        md = Path(args[0]).read_text(encoding="utf-8")
        urls = [
            line.strip().lstrip("- ").strip()
            for line in md.splitlines()
            if line.strip() and not line.strip().startswith("#")
            and line.strip().lstrip("- ").startswith("http")
        ]
        print(f"Read {len(urls)} URL(s) from {args[0]}")
        return urls
    return args


if __name__ == "__main__":
    urls = resolve_urls(sys.argv[1:])

    if urls:
        txt_paths = step_fetch(urls)
        step_extract(txt_paths)
    else:
        print("No URLs provided — skipping fetch/extract, using existing offer files.")

    step_load()
    step_dbt()
    gaps = step_score()
    if gaps:
        step_recommend(gaps)

    print("\n── Done ──────────────────────────────────────────\n")
