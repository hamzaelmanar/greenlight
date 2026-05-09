"""
run.py -- Greenlight CLI
Usage: python run.py [--mode llm|fallback]

Runs the pipeline once with no filters and prints top gaps to stdout.
For interactive use, run the Streamlit app instead.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import duckdb
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from ingestion.load_to_duckdb import load
from scoring.gap_score import get_top_gaps
from scoring.llm_hook import generate

DB_PATH = ROOT / "data" / "greenlight.duckdb"


def main():
    parser = argparse.ArgumentParser(description="Greenlight CLI")
    parser.add_argument("--mode", choices=["llm", "fallback"], default="fallback")
    args = parser.parse_args()

    print("Loading offers from lead-gen...")
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    offer_count = load(con)
    con.close()

    if offer_count == 0:
        print("No offers found. Check LEAD_GEN_PATH in .env.")
        sys.exit(1)

    print(f"{offer_count} offers loaded.")
    gaps = get_top_gaps(10)

    print("\nTop skill gaps:")
    for g in gaps:
        print(f"  {g['skill']:<30} {g['offer_count']} offers")

    print(f"\nGenerating recommendation ({args.mode} mode)...")
    rec = generate(gaps, mode=args.mode)
    print(f"\nHook: {rec['hook']}")
    print(f"\nContext:\n{rec['context']}")
    print(f"\nProject spec:\n{rec['project_spec']}")


if __name__ == "__main__":
    main()
