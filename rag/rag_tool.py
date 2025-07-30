"""Tools for querying the RAG index."""

from __future__ import annotations

from typing import Any
import os

from dotenv import load_dotenv
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.postprocessor.llm_rerank import LLMRerank
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.openai import OpenAI

from . import get_index

load_dotenv()

RAG_MODEL = os.getenv("RAG_MODEL", "gpt-4o-mini-realtime-preview-2024-12-17")

CHOICE_SELECT_PROMPT = PromptTemplate(
    (
        "A list of documents is shown below. Each document has a number next to it along "
        "with a summary of the document. A question is also provided. \n"
        "Respond with the numbers of the documents you should consult to answer the question, "
        "in order of relevance, as well as the relevance score. The relevance score is a number "
        "from 1-10 based on how relevant you think the document is to the question.\n"
        "Do not include any documents that are not relevant to the question or ranks less than 5.\n"
        "Example format: \n"
        "Document 1:\n<summary of document 1>\n\n"
        "Document 2:\n<summary of document 2>\n\n"
        "...\n\n"
        "Document 10:\n<summary of document 10>\n\n"
        "Question: <question>\n"
        "Answer:\n"
        "Doc: 9, Relevance: 7\n"
        "Doc: 3, Relevance: 4\n"
        "Doc: 7, Relevance: 3\n\n"
        "Let's try this now:\n\n"
        "{context_str}\n"
        "Question: {query_str}\n"
        "Answer:\n"
    )
)


def query_rag(query: str, top_k: int = 10, top_n: int = 3) -> Any:
    """Query the RAG index and return the reranked response."""
    index = get_index()
    retriever = index.as_retriever(similarity_top_k=top_k)
    reranker = LLMRerank(llm=OpenAI(model=RAG_MODEL), top_n=top_n, choice_select_prompt=CHOICE_SELECT_PROMPT)
    postprocessors = [SimilarityPostprocessor(similarity_cutoff=0.0), reranker]
    engine = index.as_query_engine(retriever=retriever, node_postprocessors=postprocessors)
    response = engine.query(query)
    return response
