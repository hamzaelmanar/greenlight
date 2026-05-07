"""
gap_score.py
Usage: python scoring/gap_score.py
Reads persona_gap from DuckDB and returns top N gaps as a list of dicts.
"""

from pathlib import Path
import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "greenlight.duckdb"


def get_top_gaps(n: int = 10) -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(f"""
        select skill, offer_count, gap_score, proficiency_label
        from persona_gap
        where gap_score > 0
        order by gap_score desc
        limit {n}
    """).fetchall()
    con.close()
    return [
        {"skill": r[0], "offer_count": r[1], "gap_score": r[2], "proficiency": r[3]}
        for r in rows
    ]


if __name__ == "__main__":
    gaps = get_top_gaps()
    print("\nTop skill gaps:")
    print(f"{'Skill':<20} {'Offers':>8} {'Gap score':>12} {'Your level':<12}")
    print("-" * 56)
    for g in gaps:
        print(f"{g['skill']:<20} {g['offer_count']:>8} {g['gap_score']:>12} {g['proficiency']:<12}")
