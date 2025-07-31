"""RAG utilities using LlamaIndex and Qdrant."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from llama_index.callbacks.openinference import OpenInferenceCallbackHandler
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.callbacks import LlamaDebugHandler
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

from rag.ParagraphSplitter import ParagraphSplitter

load_dotenv()

# Default directory containing documents for the RAG index. The path is
# resolved relative to the package so it works regardless of the current
# working directory.
RAG_COLLECTION = os.getenv("RAG_COLLECTION")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
OPENAI_EMBEDDING_SIZE = int(os.getenv("OPENAI_EMBEDDING_SIZE"))
FASTEMBED_SPARSE_MODEL = os.getenv("FASTEMBED_SPARSE_MODEL")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_DOCS_DIR = os.path.join(BASE_DIR, os.getenv("RAG_DOCS_DIR"))

print("RAG_DOCS_DIR: ", RAG_DOCS_DIR)

_index: Optional[VectorStoreIndex] = None

def get_index() -> VectorStoreIndex:
    """Load or create the RAG index."""
    global _index
    if _index is not None:
        return _index

    docs = SimpleDirectoryReader(input_dir=RAG_DOCS_DIR,
                                 required_exts=[".txt"],
                                 filename_as_id=True).load_data()

    splitter = ParagraphSplitter(separator=r'\n{2,}')
    nodes = splitter.get_nodes_from_documents(docs)
    print("Nodes: ", len(nodes))


    # see: https://docs.llamaindex.ai/en/stable/examples/vector_stores/qdrant_hybrid/
    client = QdrantClient(path=":memory:")
    #aclient = AsyncQdrantClient(path=":memory:")

    if not client.collection_exists(RAG_COLLECTION):
        client.create_collection(
            collection_name=RAG_COLLECTION,
            vectors_config={
                "text-dense": VectorParams(
                    size=OPENAI_EMBEDDING_SIZE,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "text-sparse": SparseVectorParams(
                    index=SparseIndexParams()
                )
            },
        )

    vector_store = QdrantVectorStore(client=client,
                                     #aclient=aclient, no es posible con qdrant en memoria!
                                     collection_name=RAG_COLLECTION,
                                     enable_hybrid=True,
                                     fastembed_sparse_model=FASTEMBED_SPARSE_MODEL)
    storage = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = OpenAIEmbedding(model=OPENAI_EMBEDDING_MODEL,
                                  dimensions=OPENAI_EMBEDDING_SIZE)
    # Callback handlers
    llama_debug = LlamaDebugHandler(print_trace_on_end=True)
    inference_handler = OpenInferenceCallbackHandler()
    Settings.callback_manager.set_handlers([llama_debug, inference_handler])

    # Arize Phoenix Instrumentor
    tracer_provider = register()
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    _index = VectorStoreIndex(nodes,
                              storage_context=storage,
                              embed_model=embed_model,
                              show_progress=True,
                              use_async=False) # no es posible con qdrant en memoria!
    return _index

# Autoload index when the module is imported
get_index()
