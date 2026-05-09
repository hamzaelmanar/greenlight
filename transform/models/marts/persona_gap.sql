-- persona_gap.sql
-- Skills missing from the candidate across filtered offers, ranked by frequency.
-- Gap signal comes from lead-gen's Mistral-computed missing_skills field —
-- already personalized per offer, no persona table join needed.

select
    skill,
    offer_count,
    total_mentions,
    offer_count as gap_score   -- frequency IS the gap: higher = build this first
from {{ ref('skill_frequency') }}
order by gap_score desc
