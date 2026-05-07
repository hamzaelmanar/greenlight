# Greenlight — v0 Architecture
> "Get the greenlight to apply."
> Portfolio gap advisor with privacy-preserving persona inference.

Started: April 29, 2026
Author: Hamza

---

## What it does

You drop in your persona (what you've built, what you know) and paste job offer URLs.
Greenlight tells you which project to build next to get hired at that type of company.

Frontend output sentence:
> "[Company] needs [data architecture / project type] to [verb] their [outcome]."

---

## Core loop

```
user persona (.md file)
  + job offers (pasted URLs → fetched → parsed)
  → dbt gap analysis (skill_frequency, persona_gap)
  → Python gap scorer
  → LLM hook (one API call → positioning sentence)
  → Streamlit UI output: project spec card
```

---

## MVP scope (2 weeks)

One complete loop, fully manual inputs, CLI-runnable, Streamlit frontend.
No auth, no database server, no scraper. Ship fast, demo fast.

**In scope:**
- .md persona template upload
- Manual URL paste (job offers)
- URL fetch + skill extraction (Python)
- DuckDB + dbt transformation layer
- Gap scoring (Python, set diff + weighting)
- LLM sentence generation (one structured API call)
- Streamlit frontend (upload + paste + view result)
- Demo video → LinkedIn pillar post ~May 13

**Out of scope for MVP:**
- GitHub/LinkedIn/X persona parsing
- Live scraper (WTTJ/Indeed/APEC)
- TEE privacy layer
- Auth / user accounts
- Multi-user persistence

---

## Stack

| Layer | Tool | Reason |
|---|---|---|
| Job offer fetch | Python + requests + BeautifulSoup | URL → raw HTML → text |
| Skill extraction | Python + regex / spaCy / LLM | Extract tools, domains, seniority from offer text |
| Local warehouse | **DuckDB** | Zero setup, file-based, SQL-native, growing AE skill |
| Transformation | **dbt (dbt-duckdb adapter)** | Same dbt skills, new adapter — demonstrates generalizability |
| Gap scoring | Python | Persona skills vs. market skill frequency |
| LLM hook | OpenAI API (structured output) | One call, generates the positioning sentence |
| Frontend | **Streamlit** | Python-native, zero frontend knowledge needed, deploys in one command |

---

## Persona template (v1 — the first user input)

```markdown
## Skills
# tool | proficiency (1-3) | used in production?
dbt | 2 | yes
Airflow | 2 | yes
PostgreSQL | 2 | yes
Python | 2 | yes
Spark | 0 | no

## Projects built
# name | domain | pipeline stages covered | dbt concepts used
financial-data-platform | DeFi/LP analytics | ingestion+transform+test | surrogate keys, window functions, generic tests

## Target roles
Analytics Engineer, Data Engineer

## Domain preferences
fintech, marketing analytics, product analytics

## What I want to learn next
DuckDB, LLM pipelines, streaming basics

## Time available for a project
~2 weeks
```

Filling this in is a standalone value — forces honest self-assessment before the tool runs.

---

## dbt data model

### Sources
- `raw.job_offers` — fetched offer text, URL, date scraped, company name
- `raw.persona` — parsed persona fields from .md template

### Staging
- `stg_job_offers` — cleaned offer text, extracted skill list (array), domain, seniority, company
- `stg_persona` — normalized skill list, proficiency scores, domain preferences

### Marts
- `fct_skill_frequency` — skill | count | % of offers | domain | seniority
- `fct_persona_gap` — skill | in_persona | in_market | frequency_rank | gap_score
- `fct_project_recommendations` — ranked project suggestions with stack, domain, estimated hours

---

## Streamlit frontend flow

```
[1] Upload persona.md
      ↓
[2] Paste job offer URLs (one per line)
      ↓
[3] Click "Analyze"
      → fetch offers → run dbt → score gap → call LLM
      ↓
[4] Output card:
    ┌─────────────────────────────────────────────┐
    │ [Company type] needs [project type]          │
    │ to [verb] their [outcome].                   │
    │                                              │
    │ Build: [project name]                        │
    │ Stack: dbt · DuckDB · Airflow · Python       │
    │ Teaches: [skill 1], [skill 2]                │
    │ Covers [X]% of your target offers            │
    │ Estimated: ~2 weeks                          │
    └─────────────────────────────────────────────┘
```

---

## 2-week build plan

**Week 1 (May 5–11):**
- Day 1–2: persona template + DuckDB setup + dbt-duckdb project scaffold
- Day 3–4: job offer parser (URL → raw JSON → `stg_job_offers`)
- Day 5: dbt marts (`fct_skill_frequency`, `fct_persona_gap`)

**Week 2 (May 12–18):**
- Day 1–2: gap scorer (Python, persona vs. market frequency)
- Day 3: LLM hook (structured output → positioning sentence)
- Day 4: Streamlit frontend
- Day 5: polish + record demo video → LinkedIn pillar post ~May 13

---

## Future iterations (post-MVP)

- GitHub repo parsing → auto-build persona (no .md needed)
- LinkedIn profile parsing
- Live job offer scraping (WTTJ, Indeed, APEC) via scheduled Airflow DAG
- TEE integration (Phala / AWS Nitro) — persona never leaves enclave
- Persona form (structured input as alternative to .md upload)
- Multi-role support (PM, ML engineer, frontend, etc.)
- Public deployment (Streamlit Cloud or Hugging Face Spaces)

---

## Why this project works for CDI positioning

| What you build | What recruiter sees |
|---|---|
| URL fetch + HTML parsing | API / web ingestion pipeline |
| DuckDB + dbt-duckdb | DWH-agnostic transformation skills |
| dbt staging/marts on job offer data | Data modeling on real-world text data |
| LLM structured output call | Modern DE/AE toolchain awareness |
| Streamlit demo | End-to-end: data in → insight out |

The domain (job offers) is universally relatable. Every recruiter understands the problem. That's the CDI unlock vs. the LP project.
