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


def get_cohort_names() -> list[tuple[str, str, str]]:
    """Return (run_id, cohort_name, run_at) for all runs that have cohort_skills data."""
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        rows = con.execute("""
            select r.run_id,
                   json_extract_string(r.filters, '$.cohort') as cohort_name,
                   strftime(r.run_at, '%Y-%m-%d %H:%M') as run_at
            from run_log r
            where exists (select 1 from cohort_skills c where c.run_id = r.run_id)
            order by r.run_at desc
            limit 20
        """).fetchall()
        con.close()
        return [(r[0], r[1] or r[0][:8], r[2]) for r in rows]
    except Exception:
        return []


def get_cohort_comparison(run_id_a: str, run_id_b: str) -> list[dict]:
    """
    Pivot cohort_skills for two runs side by side.
    Returns rows: {skill, has_skill, a_count, b_count}
    where a_count / b_count = number of offers in that cohort demanding the skill.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute("""
        with all_skills as (
            select skill, has_skill from cohort_skills where run_id = ?
            union
            select skill, has_skill from cohort_skills where run_id = ?
        ),
        a as (
            select skill, has_skill, count(distinct offer_id) as cnt
            from cohort_skills where run_id = ? group by skill, has_skill
        ),
        b as (
            select skill, has_skill, count(distinct offer_id) as cnt
            from cohort_skills where run_id = ? group by skill, has_skill
        )
        select
            s.skill,
            s.has_skill,
            coalesce(a.cnt, 0) as a_count,
            coalesce(b.cnt, 0) as b_count
        from (select distinct skill, has_skill from all_skills) s
        left join a using (skill, has_skill)
        left join b using (skill, has_skill)
        order by s.has_skill asc, (coalesce(a.cnt,0) + coalesce(b.cnt,0)) desc
    """, [run_id_a, run_id_b, run_id_a, run_id_b]).fetchall()
    con.close()
    return [
        {"skill": r[0], "has_skill": r[1], "a_count": r[2], "b_count": r[3]}
        for r in rows
    ]


if __name__ == "__main__":
    gaps = get_top_gaps()
    print("\nTop skill gaps:")
    print(f"{'Skill':<20} {'Offers':>8} {'Gap score':>12}")
    print("-" * 44)
    for g in gaps:
        print(f"{g['skill']:<20} {g['offer_count']:>8} {g['gap_score']:>12}")
