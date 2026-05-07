# Greenlight

<h3 align="center">"Get the greenlight to apply."</h3>

Technical portfolio gap advisor for data and analytics engineers.

## How it works

```
persona.md + job offer URLs
  → fetch + skill extraction
  → DuckDB + dbt (staging → marts)
  → Python gap scorer
  → LLM recommendation (Mistral)
  → Streamlit UI output
```

## Stack

| Layer | Tool |
|---|---|
| Frontend | Streamlit |
| Transformation | dbt-duckdb |
| Local warehouse | DuckDB |
| Skill extraction | Python + BeautifulSoup |
| LLM hook | Mistral AI |

## Local setup

**Requirements:** Python 3.10+

```bash
# 1. Clone and create virtual environment
git clone https://github.com/your-username/greenlight.git
cd greenlight
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your Mistral API key:
# MISTRAL_API_KEY=your_key_here

# 4. Run the app
streamlit run app/streamlit_app.py
```

## Usage

1. Open the Streamlit app in your browser.
2. Upload your persona file (see `persona/hamza.md` as reference).
3. Paste job offer URLs (one per line, or use `offers.md` format).
4. Select LLM mode and click **Run**.
5. View your top skill gaps and the recommended next project to build.

## Persona format

Create a Markdown file following this structure:

```markdown
## Skills
# tool | proficiency (1-3) | used in production?
dbt | 2 | yes
Python | 3 | yes

## Projects built
# name | domain | pipeline stages covered | dbt concepts used
my-project | fintech | ingestion+transform+test | surrogate keys, window functions

## Target roles
Analytics Engineer, Data Engineer

## Domain preferences
fintech, marketing analytics

## What I want to learn next
DuckDB, LLM pipelines

## Time available for a project
~2 weeks
```

## CLI usage

```bash
python run.py "https://wttj.co/offer1" "https://wttj.co/offer2"
# or pass a file of URLs
python run.py offers.md
```

## Project structure

```
app/              Streamlit frontend
ingestion/        Fetch, parse, and load offer data
scoring/          Gap scoring logic and LLM hook
transform/        dbt project (staging → marts)
persona/          Persona Markdown files
data/             DuckDB database (gitignored, created at runtime)
offers/           Cached offer text and extracted skills (gitignored)
```
