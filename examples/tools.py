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


def query_rag() -> str:
    # TODO: call query_rag() in rag_tool
    return "TEST"