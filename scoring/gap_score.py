"""
gap_score.py
Aggregates missing_skills frequency directly from raw_offer_skills in DuckDB.
No dbt run required — the aggregation is trivial and runs inline.
"""

from pathlib import Path
import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "greenlight.duckdb"


def get_top_gaps(n: int = 10) -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(f"""
        select
            skill,
            count(distinct offer_id) as offer_count,
            count(distinct offer_id) as gap_score
        from raw_offer_skills
        group by skill
        order by gap_score desc
        limit {n}
    """).fetchall()
    con.close()
    return [
        {"skill": r[0], "offer_count": r[1], "gap_score": r[2]}
        for r in rows
    ]


if __name__ == "__main__":
    gaps = get_top_gaps()
    print("\nTop skill gaps:")
    print(f"{'Skill':<20} {'Offers':>8} {'Gap score':>12}")
    print("-" * 44)
    for g in gaps:
        print(f"{g['skill']:<20} {g['offer_count']:>8} {g['gap_score']:>12}")
