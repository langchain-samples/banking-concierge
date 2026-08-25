"""Vector-store retrieval over the synthetic banking knowledge base."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

KB_DIR = Path(__file__).parent / "kb"

logger = logging.getLogger(__name__)


def _make_embeddings() -> OpenAIEmbeddings:
    """Create an OpenAIEmbeddings instance pinned to the OpenAI API."""
    # Embeddings must go directly to OpenAI. The LangSmith gateway only
    # allow-lists chat completions, not /embeddings, so when BASE_URL /
    # OPENAI_BASE_URL point at the gateway (as they do for the chat model in
    # graph.py) an embeddings client that inherits them gets a 404 for the
    # missing text-embedding-3-small deployment. LANGSMITH_API_KEY is a gateway
    # credential and must never be passed as the OpenAI api_key here.
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=os.environ["OPENAI_API_KEY"],
    )


def _load_kb_documents() -> list[Document]:
    docs: list[Document] = []
    for md_path in sorted(KB_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=text,
                metadata={"source": md_path.name, "topic": md_path.stem},
            )
        )
    return docs


@lru_cache(maxsize=1)
def get_vector_store() -> InMemoryVectorStore:
    docs = _load_kb_documents()
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    chunks = splitter.split_documents(docs)
    # lru_cache only stores successful returns, so re-raising here leaves the
    # cache empty and a later call retries once credentials are fixed.
    try:
        embeddings = _make_embeddings()
        return InMemoryVectorStore.from_documents(chunks, embeddings)
    except Exception:
        logger.exception("Failed to build the banking documentation index")
        raise


def retrieve(query: str, k: int = 4) -> list[Document]:
    return get_vector_store().similarity_search(query, k=k)
