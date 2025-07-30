"""RAG utilities using LlamaIndex and Qdrant."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

load_dotenv()

RAG_DOCS_DIR = os.getenv("RAG_DOCS_DIR", "./rag_docs")
RAG_COLLECTION = os.getenv("RAG_COLLECTION", "rag_collection_name")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

_index: Optional[VectorStoreIndex] = None


def get_index() -> VectorStoreIndex:
    """Load or create the RAG index."""
    global _index
    if _index is not None:
        return _index

    docs = SimpleDirectoryReader(RAG_DOCS_DIR).load_data()
    splitter = SentenceSplitter()
    nodes = splitter.get_nodes_from_documents(docs)

    client = QdrantClient(path=":memory:")
    vector_store = QdrantVectorStore(client=client, collection_name=RAG_COLLECTION)
    storage = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = OpenAIEmbedding(model=OPENAI_EMBEDDING_MODEL)
    _index = VectorStoreIndex(nodes, storage_context=storage, embed_model=embed_model)
    return _index
