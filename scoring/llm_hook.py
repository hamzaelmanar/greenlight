"""
llm_hook.py
Generates a positioning sentence + project spec card from gap data.

Two modes:
- fallback: pure template logic, no API call
- llm: Mistral API (mistral-small-latest), structured JSON output
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# --- Skill → human-readable label ---
SKILL_LABELS = {
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "dbt": "dbt",
    "airflow": "Airflow",
    "spark": "Apache Spark",
    "terraform": "Terraform",
    "tableau": "Tableau",
    "looker": "Looker",
    "metabase": "Metabase",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "aws": "AWS",
    "gcp": "GCP",
    "python": "Python",
    "sql": "SQL",
    "kafka": "Kafka",
    "fastapi": "FastAPI",
    "streamlit": "Streamlit",
}

# Skill → what kind of project demonstrates it best
SKILL_TO_PROJECT = {
    "snowflake":  "a dbt project on a Snowflake free-trial account — staging + mart models, tests, and a lineage screenshot",
    "bigquery":   "a dbt project on BigQuery sandbox — same dbt patterns you already know, new warehouse",
    "tableau":    "a Tableau Public dashboard connected to a public dataset with at least one calculated field",
    "looker":     "a LookML project on Looker's free developer instance with one Explore and one dashboard",
    "metabase":   "a Metabase instance (Docker) connected to a local DuckDB or Postgres, with a question and dashboard",
    "spark":      "a PySpark pipeline on a local or Databricks Community Edition cluster processing a public dataset",
    "terraform":  "a Terraform module that provisions a cloud storage bucket + a managed database (any cloud free tier)",
    "kubernetes": "a Docker Compose → Kubernetes migration of an existing project using minikube",
    "aws":        "an AWS project using S3 + Lambda or Glue to move and transform a dataset end-to-end",
    "gcp":        "a GCP project using Cloud Storage + BigQuery + a scheduled query or Dataflow job",
    "kafka":      "a local Kafka producer/consumer pipeline using Docker Compose, processing a public stream",
    "airflow":    "an Airflow DAG orchestrating an existing pipeline (you already have this — show it)",
    "dbt":        "a new dbt project on a different adapter (you're doing this now with dbt-duckdb — ship it)",
}

# Skill → market context sentence
SKILL_CONTEXT = {
    "snowflake":  "Snowflake dominates cloud data warehouse adoption in French scaleups and mid-market companies.",
    "bigquery":   "BigQuery is the default warehouse for GCP-native stacks, common in fintech and e-commerce.",
    "tableau":    "Tableau remains the most requested BI tool across analyst and AE roles in Paris.",
    "looker":     "Looker adoption is growing in product-led companies moving toward self-serve analytics.",
    "metabase":   "Metabase is the go-to BI layer for early-stage and mid-stage product companies.",
    "spark":      "Spark appears in DE roles at companies processing large volumes of event or transactional data.",
    "terraform":  "Terraform is required in DE roles with infrastructure ownership, especially at cloud-native companies.",
    "kubernetes": "Kubernetes appears in senior DE roles at companies running containerised data workloads.",
    "aws":        "AWS is the most common cloud provider in the Paris job market across all seniority levels.",
    "gcp":        "GCP appears heavily in roles at companies already using BigQuery or Google Workspace.",
    "kafka":      "Kafka surfaces in real-time pipeline roles, mostly at companies with high event volume.",
    "airflow":    "Airflow is the orchestration standard — you already have it, highlight it more explicitly.",
    "dbt":        "dbt is in 10 of your 15 offers. It's table stakes — your existing project already covers this.",
}


def _label(skill: str) -> str:
    return SKILL_LABELS.get(skill, skill.title())


def generate_fallback(gaps: list[dict], target_roles: list[str]) -> dict:
    """
    gaps: output of get_top_gaps() — list of {skill, offer_count, gap_score, proficiency}
    target_roles: e.g. ["Analytics Engineer", "Data Engineer"]
    Returns a dict with: hook, context, project_spec, top_gaps
    """
    if not gaps:
        return {
            "hook": "No gaps found. Load more job offers to get a recommendation.",
            "context": "",
            "project_spec": "",
            "top_gaps": [],
        }

    top = gaps[0]
    second = gaps[1] if len(gaps) > 1 else None
    role = target_roles[0] if target_roles else "data professional"

    # --- Hook sentence ---
    if second:
        hook = (
            f"To get hired as a {role} in this market, "
            f"build a project that demonstrates {_label(top['skill'])} "
            f"and {_label(second['skill'])} working together."
        )
    else:
        hook = (
            f"To get hired as a {role} in this market, "
            f"build a project that demonstrates {_label(top['skill'])}."
        )

    # --- Market context ---
    context_lines = []
    for g in gaps[:3]:
        ctx = SKILL_CONTEXT.get(g["skill"])
        if ctx:
            context_lines.append(f"- **{_label(g['skill'])}** ({g['offer_count']} offers): {ctx}")
    context = "\n".join(context_lines)

    # --- Project spec ---
    spec = SKILL_TO_PROJECT.get(top["skill"])
    if spec:
        project_spec = f"**Build:** {spec}"
        if second:
            spec2 = SKILL_TO_PROJECT.get(second["skill"])
            if spec2:
                project_spec += f"\n**Or combine:** {spec2} — then layer {_label(top['skill'])} as the warehouse."
    else:
        project_spec = f"Build a project that uses {_label(top['skill'])} end-to-end and publish it on GitHub."

    return {
        "hook": hook,
        "context": context,
        "project_spec": project_spec,
        "top_gaps": gaps[:5],
    }


def generate_llm(gaps: list[dict], target_roles: list[str]) -> dict:
    """Call Mistral (mistral-small-latest) for a richer, context-aware recommendation."""
    from mistralai.client import Mistral

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set in .env")

    client = Mistral(api_key=api_key)

    gaps_table = "\n".join(
        f"- {g['skill']}: {g['offer_count']} offers, gap_score={g['gap_score']}, your level={g['proficiency']}"
        for g in gaps[:8]
    )
    roles = ", ".join(target_roles)

    prompt = f"""You are a career advisor for data professionals.

The user is targeting these roles: {roles}

Here are their top skill gaps (skills the market wants that they lack or are weak on):
{gaps_table}

Based on this, respond with a JSON object with exactly these keys:
- "hook": one punchy sentence (max 25 words) telling them what to build to get hired
- "context": 2-3 sentences explaining why these gaps matter in the current market
- "project_spec": a concrete project they can build in under 2 weeks that closes the biggest gap(s), described in 2-3 sentences

Return only valid JSON, no markdown, no explanation outside the JSON."""

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=400,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    return {
        "hook": parsed.get("hook", ""),
        "context": parsed.get("context", ""),
        "project_spec": parsed.get("project_spec", ""),
        "top_gaps": gaps[:5],
    }


def generate(gaps: list[dict], target_roles: list[str], mode: str = "llm") -> dict:
    if mode == "fallback":
        return generate_fallback(gaps, target_roles)
    if mode == "llm":
        return generate_llm(gaps, target_roles)
    raise NotImplementedError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    # Smoke test with fake data
    fake_gaps = [
        {"skill": "snowflake", "offer_count": 7, "gap_score": 7.0, "proficiency": "none"},
        {"skill": "tableau",   "offer_count": 6, "gap_score": 6.0, "proficiency": "none"},
        {"skill": "bigquery",  "offer_count": 5, "gap_score": 5.0, "proficiency": "none"},
    ]
    result = generate(fake_gaps, ["Analytics Engineer", "Data Engineer"])
    print("\n── Greenlight recommendation ─────────────────────\n")
    print(result["hook"])
    print()
    print(result["context"])
    print()
    print(result["project_spec"])
    print()
