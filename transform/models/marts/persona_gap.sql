-- persona_gap.sql
-- Left joins market skill frequency against the persona.
-- Skills the market wants but the persona is weak on = gaps.

with market as (
    select * from {{ ref('skill_frequency') }}
),

persona as (
    select * from {{ ref('stg_persona_skills') }}
)

select
    m.skill,
    m.offer_count,
    m.total_mentions,
    coalesce(p.proficiency, 0)          as persona_proficiency,
    coalesce(p.in_production, false)    as persona_in_production,
    coalesce(p.proficiency_label, 'none') as proficiency_label,

    -- Gap score: high offer_count + low persona_proficiency = biggest gap
    round(
        m.offer_count * (1.0 - coalesce(p.proficiency, 0) / 3.0),
        2
    )                                   as gap_score

from market m
left join persona p on m.skill = p.skill
order by gap_score desc
