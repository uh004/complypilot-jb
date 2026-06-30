"""Project paths and environment helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def find_project_root(start_path: Path | None = None) -> Path:
    current_path = (start_path or Path.cwd()).resolve()

    for path in [current_path, *current_path.parents]:
        if (path / "data").exists() and ((path / "README.md").exists() or (path / "AGENTS.md").exists()):
            return path

    return current_path


PROJECT_ROOT = find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
RULES_DIR = DATA_DIR / "rules"
PRODUCTS_DIR = DATA_DIR / "products"
RETRIEVAL_DIR = DATA_DIR / "retrieval"
BM25_DIR = RETRIEVAL_DIR / "bm25_index"
REGULATIONS_DIR = DATA_DIR / "regulations"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
CHROMA_DB_DIR = DATA_DIR / "chromadb"
REGULATION_PDF_DIR = DATA_DIR / "vectordb"
VECTORDB_DIR = REGULATION_PDF_DIR
PARENTS_PATH = RETRIEVAL_DIR / "parents.jsonl"
CHILDREN_PATH = RETRIEVAL_DIR / "children.jsonl"
BM25_PATH = BM25_DIR / "bm25.pkl"
COLLECTION_NAME = "complypilot_regulations_v2"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"


def ensure_project_dirs() -> None:
    for directory in [
        DATA_DIR,
        RULES_DIR,
        PRODUCTS_DIR,
        RETRIEVAL_DIR,
        BM25_DIR,
        REGULATIONS_DIR,
        SAMPLES_DIR,
        OUTPUTS_DIR,
        REPORTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


ensure_project_dirs()
load_project_env()
