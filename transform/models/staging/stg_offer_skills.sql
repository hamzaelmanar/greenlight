-- stg_offer_skills.sql
-- One row per (offer, skill) with normalised skill name.

select
    offer_id,
    lower(skill) as skill,
    mention_count
from {{ source('raw', 'raw_offer_skills') }}
where mention_count > 0
