"""
llm_hook.py
Generates a positioning sentence + project spec card from gap data.

Two modes:
- fallback: pure template logic, no API call
- llm: Mistral API (mistral-small-latest), structured JSON output

Both modes accept:
  gaps         : list[dict]  -- [{skill, offer_count, gap_score}, ...]
  filter_ctx   : str         -- e.g. "12 offers - consulting - Paris - seniority <= stretch"
  persona_prose: str | None  -- full text of lead-gen persona.md (llm mode only)
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# --- Skill -> human-readable label ---
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

# Skill -> what kind of project demonstrates it best
SKILL_TO_PROJECT = {
    "snowflake":  "a dbt project on a Snowflake free-trial account -- staging + mart models, tests, and a lineage screenshot",
    "bigquery":   "a dbt project on BigQuery sandbox -- same dbt patterns you already know, new warehouse",
    "tableau":    "a Tableau Public dashboard connected to a public dataset with at least one calculated field",
    "looker":     "a LookML project on Looker free developer instance with one Explore and one dashboard",
    "metabase":   "a Metabase instance (Docker) connected to a local DuckDB or Postgres, with a question and dashboard",
    "spark":      "a PySpark pipeline on a local or Databricks Community Edition cluster processing a public dataset",
    "terraform":  "a Terraform module that provisions a cloud storage bucket + a managed database (any cloud free tier)",
    "kubernetes": "a Docker Compose to Kubernetes migration of an existing project using minikube",
    "aws":        "an AWS project using S3 + Lambda or Glue to move and transform a dataset end-to-end",
    "gcp":        "a GCP project using Cloud Storage + BigQuery + a scheduled query or Dataflow job",
    "kafka":      "a local Kafka producer/consumer pipeline using Docker Compose, processing a public stream",
    "airflow":    "an Airflow DAG orchestrating an existing pipeline (you already have this -- show it)",
    "dbt":        "a new dbt project on a different adapter (you are doing this now with dbt-duckdb -- ship it)",
}

# Skill -> market context sentence
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
    "airflow":    "Airflow is the orchestration standard -- you already have it, highlight it more explicitly.",
    "dbt":        "dbt is in most of your filtered offers. It is table stakes -- your existing project already covers this.",
}


def _label(skill: str) -> str:
    return SKILL_LABELS.get(skill, skill.title())


def generate_fallback(
    gaps: list[dict],
    filter_ctx: str = "",
    **_kwargs,
) -> dict:
    """Template-only recommendation, no API call."""
    if not gaps:
        return {
            "hook": "No gaps found. Adjust your filters or add more offers in lead-gen.",
            "context": "",
            "project_spec": "",
            "top_gaps": [],
        }

    top = gaps[0]
    second = gaps[1] if len(gaps) > 1 else None
    scope = f" ({filter_ctx})" if filter_ctx else ""

    if second:
        hook = (
            f"To get hired in this segment{scope}, "
            f"build a project combining {_label(top['skill'])} and {_label(second['skill'])}."
        )
    else:
        hook = (
            f"To get hired in this segment{scope}, "
            f"build a project that demonstrates {_label(top['skill'])}."
        )

    context_lines = []
    for g in gaps[:3]:
        ctx = SKILL_CONTEXT.get(g["skill"])
        if ctx:
            context_lines.append(f"- **{_label(g['skill'])}** ({g['offer_count']} offers): {ctx}")
    context = "\n".join(context_lines)

    spec = SKILL_TO_PROJECT.get(top["skill"])
    if spec:
        project_spec = f"**Build:** {spec}"
        if second:
            spec2 = SKILL_TO_PROJECT.get(second["skill"])
            if spec2:
                project_spec += f"\n**Or combine:** {spec2} -- then layer {_label(top['skill'])} as the warehouse."
    else:
        project_spec = f"Build a project that uses {_label(top['skill'])} end-to-end and publish it on GitHub."

    return {
        "hook": hook,
        "context": context,
        "project_spec": project_spec,
        "top_gaps": gaps[:5],
    }


def generate_llm(
    gaps: list[dict],
    filter_ctx: str = "",
    persona_prose: str | None = None,
    **_kwargs,
) -> dict:
    """Call Mistral for a richer, context-aware recommendation."""
    from mistralai.client import Mistral

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set in .env")

    client = Mistral(api_key=api_key)

    gaps_table = "\n".join(
        f"- {g['skill']}: appears in {g['offer_count']} offer(s) where you are missing it"
        for g in gaps[:8]
    )

    persona_section = (
        f"\nCandidate profile:\n{persona_prose.strip()}\n"
        if persona_prose else ""
    )

    scope_line = (
        f"\nThese gaps are computed from a filtered subset of job offers: {filter_ctx}."
        if filter_ctx else ""
    )

    prompt = f"""You are a career advisor for data professionals targeting Analytics Engineer and Data Engineer roles in France.
{persona_section}
The following skills appear most frequently in job offers where the candidate is identified as missing them:{scope_line}

{gaps_table}

Based on this, respond with a JSON object with exactly these keys:
- "hook": one punchy sentence (max 25 words) telling them what to build to get hired in this specific market segment
- "context": 2-3 sentences explaining why these gaps matter for this type of role / location
- "project_spec": a plain string (NOT a nested object) describing a concrete project they can build in under 2 weeks — include tools, deliverable, and 2-3 steps inline in the text

All values must be strings or arrays of strings. Do NOT nest objects inside project_spec.
Return only valid JSON, no markdown, no explanation outside the JSON."""

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    project_spec = parsed.get("project_spec", "")
    # Normalize to str — LLM sometimes returns a nested dict despite instructions
    if isinstance(project_spec, str) and project_spec.strip().startswith("{"):
        import ast
        try:
            project_spec = json.loads(project_spec)
        except json.JSONDecodeError:
            try:
                project_spec = ast.literal_eval(project_spec)
            except Exception:
                pass
    if isinstance(project_spec, dict):
        parts = []
        if n := project_spec.get("project_name") or project_spec.get("name"):
            parts.append(f"**{n}**")
        if d := project_spec.get("deliverable") or project_spec.get("output"):
            parts.append(d)
        if tools := project_spec.get("tools"):
            parts.append("**Tools:** " + (", ".join(tools) if isinstance(tools, list) else str(tools)))
        if steps := project_spec.get("steps"):
            steps_list = steps if isinstance(steps, list) else [steps]
            parts.append("**Steps:**\n" + "\n".join(f"- {s}" for s in steps_list))
        project_spec = "\n\n".join(parts) if parts else str(project_spec)
    elif not isinstance(project_spec, str):
        project_spec = json.dumps(project_spec, ensure_ascii=False)

    return {
        "hook": parsed.get("hook", ""),
        "context": parsed.get("context", ""),
        "project_spec": project_spec,
        "top_gaps": gaps[:5],
    }


def generate(
    gaps: list[dict],
    filter_ctx: str = "",
    persona_prose: str | None = None,
    mode: str = "llm",
) -> dict:
    if mode == "fallback":
        return generate_fallback(gaps, filter_ctx=filter_ctx)
    if mode == "llm":
        try:
            return generate_llm(gaps, filter_ctx=filter_ctx, persona_prose=persona_prose)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "capacity" in msg.lower() or "rate" in msg.lower():
                result = generate_fallback(gaps, filter_ctx=filter_ctx)
                result["hook"] = "[Rate limit — fallback] " + result["hook"]
                return result
            raise
    raise NotImplementedError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    fake_gaps = [
        {"skill": "snowflake", "offer_count": 7, "gap_score": 7.0},
        {"skill": "tableau",   "offer_count": 6, "gap_score": 6.0},
        {"skill": "bigquery",  "offer_count": 5, "gap_score": 5.0},
    ]
    result = generate(fake_gaps, filter_ctx="10 offers - consulting - Paris")
    print("\n-- Greenlight recommendation -----------------\n")
    print(result["hook"])
    print()
    print(result["context"])
    print()
    print(result["project_spec"])
    print()

