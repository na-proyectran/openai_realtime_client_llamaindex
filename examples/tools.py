import os
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Atlantic/Canary")

def get_current_time() -> dict:
    """
    Devuelve la hora actual en formato HH:MM y la zona horaria configurada.
    """
    try:
        tz = ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        print(f"No time zone found with key {TIMEZONE}, falling back to UTC")
        tz = ZoneInfo("UTC")

    now = datetime.now(tz)
    h_str = now.strftime("%H")
    m_str = now.strftime("%M")
    return {
        "current_hour": h_str,
        "current_minutes": m_str,
        "timezone": TIMEZONE
    }


def get_current_date() -> dict:
    """
    Devuelve la fecha actual en formato DD:MM y la zona horaria configurada.
    """
    try:
        tz = ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        print(f"No time zone found with key {TIMEZONE}, falling back to UTC")
        tz = ZoneInfo("UTC")

    now = datetime.now(tz)
    d_str = now.strftime("%d")
    m_str = now.strftime("%m")
    return {
        "current_day": d_str,
        "current_month": m_str,
        "timezone": TIMEZONE
    }


def query_rag(query: str, top_k: int = 10, top_n: int = 3) -> str:
    """Return a response from the local RAG index.

    Parameters
    ----------
    query : str
        The query string to search for in the indexed documents.
    top_k : int, optional
        Number of documents to retrieve from the index before reranking.
    top_n : int, optional
        Number of documents to return after reranking.
    """

    from rag.rag_tool import query_rag as _query_rag

    response = _query_rag(query=query, top_k=top_k, top_n=top_n)
    return str(response)


async def aquery_rag(query: str, top_k: int = 10, top_n: int = 3) -> str:
    """Async wrapper around :func:`rag.rag_tool.aquery_rag`."""
    from rag.rag_tool import aquery_rag as _aquery_rag

    response = await _aquery_rag(query=query, top_k=top_k, top_n=top_n)
    return str(response)
