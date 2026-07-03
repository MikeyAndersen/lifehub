import os


def _list(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "dev-secret")
TELEGRAM_ALLOWED_CHAT_IDS = {int(x) for x in _list("TELEGRAM_ALLOWED_CHAT_IDS")}
TELEGRAM_ADMIN_CHAT_ID = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# Dual-pass quality review. Empty STRONG_OLLAMA_URL disables the feature
# entirely: no queueing, no extra calls, behaviour exactly as before.
STRONG_OLLAMA_URL = os.getenv("STRONG_OLLAMA_URL", "")
STRONG_OLLAMA_MODEL = os.getenv("STRONG_OLLAMA_MODEL", "qwen2.5:32b-instruct")
REVIEW_HARD_MAX_AGE_DAYS = int(os.getenv("REVIEW_HARD_MAX_AGE_DAYS", "7"))
REVIEW_DRAIN_TOKEN = os.getenv("REVIEW_DRAIN_TOKEN", "")

GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "/secrets/token.json")
DEFAULT_CALENDAR_ID = os.getenv("DEFAULT_CALENDAR_ID", "primary")
BIRTHDAYS_CALENDAR_ID = os.getenv(
    "BIRTHDAYS_CALENDAR_ID", "addressbook#contacts@group.v.calendar.google.com"
)

VIKUNJA_URL = os.getenv("VIKUNJA_URL", "http://vikunja:3456")
VIKUNJA_TOKEN = os.getenv("VIKUNJA_TOKEN", "")
VIKUNJA_DEFAULT_PROJECT_ID = int(os.getenv("VIKUNJA_DEFAULT_PROJECT_ID", "1"))
VIKUNJA_SHOPPING_PROJECT_ID = int(os.getenv("VIKUNJA_SHOPPING_PROJECT_ID", "1"))

ADMIN_EMAILS = {e.lower() for e in _list("ADMIN_EMAILS")}
TZ = os.getenv("TZ", "Europe/Copenhagen")
LATITUDE = float(os.getenv("LATITUDE", "56.15"))
LONGITUDE = float(os.getenv("LONGITUDE", "10.21"))
ELPRIS_AREA = os.getenv("ELPRIS_AREA", "DK1")

DB_PATH = os.getenv("DB_PATH", "./lifehub.db")
