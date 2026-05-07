-- stg_persona_skills.sql
-- One row per skill in the user's persona.

select
    skill,
    proficiency,
    in_production,
    case
        when proficiency = 0 then 'none'
        when proficiency = 1 then 'aware'
        when proficiency = 2 then 'used'
        when proficiency = 3 then 'strong'
    end as proficiency_label
from {{ source('raw', 'raw_persona_skills') }}
