"""
extract_skills.py
Usage: python ingestion/extract_skills.py offers/<file>.txt
Reads cleaned offer text, extracts skill mentions, prints JSON.
Also writes to offers/<slug>_skills.json for dbt seed loading.
"""

import sys
import json
import re
from pathlib import Path

# Canonical skill list — extend freely
SKILLS = [
    # Core data tools
    "dbt", "airflow", "spark", "kafka", "flink",
    # Warehouses / databases
    "bigquery", "snowflake", "redshift", "postgresql", "postgres",
    "duckdb", "clickhouse", "databricks",
    # Languages
    "python", "sql", "scala", "java", "r",
    # Cloud
    "aws", "gcp", "azure", "terraform", "docker", "kubernetes", "k8s",
    # Orchestration / infra
    "luigi", "prefect", "dagster", "mage",
    # BI / viz
    "looker", "metabase", "tableau", "power bi", "powerbi", "superset",
    # ML / LLM
    "mlflow", "sagemaker", "vertex ai", "openai", "llm", "langchain",
    # Streams
    "kinesis", "pubsub", "rabbitmq",
    # Frontend / app
    "streamlit", "fastapi", "flask", "django",
]

# Build regex: match whole words, case-insensitive
# For multi-word skills (e.g. "power bi") we match literally
_PATTERNS = {skill: re.compile(r"\b" + re.escape(skill) + r"\b", re.IGNORECASE) for skill in SKILLS}


def extract(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for skill, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            counts[skill] = len(matches)
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingestion/extract_skills.py offers/<file>.txt")
        sys.exit(1)

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    counts = extract(text)

    output_path = path.with_name(path.stem + "_skills.json")
    output_path.write_text(json.dumps(counts, indent=2), encoding="utf-8")

    print(json.dumps(counts, indent=2))
    print(f"\nSaved → {output_path}")
