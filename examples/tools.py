import os
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Atlantic/Canary")

def get_current_time() -> dict:
    """Return the current time in ISO 8601 format for the configured time zone.
    """
    try:
        tz = ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        print(f"No time zone found with key {TIMEZONE}, falling back to UTC")
        tz = ZoneInfo("UTC")
    now = datetime.now(tz=tz)
    return {"current_time": now.isoformat()}
