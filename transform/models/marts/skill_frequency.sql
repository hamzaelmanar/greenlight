-- skill_frequency.sql
-- How often each skill appears across all loaded offers.
-- This is the market signal: high frequency = market demands it.

select
    skill,
    count(distinct offer_id)                     as offer_count,
    sum(mention_count)                           as total_mentions,
    round(avg(mention_count), 2)                 as avg_mentions_per_offer
from {{ ref('stg_offer_skills') }}
group by skill
order by offer_count desc, total_mentions desc
