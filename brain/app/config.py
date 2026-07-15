import os


def _list(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "dev-secret")
TELEGRAM_ALLOWED_CHAT_IDS = {int(x) for x in _list("TELEGRAM_ALLOWED_CHAT_IDS")}
TELEGRAM_ADMIN_CHAT_ID = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
# Whisper-model til voicebeskeder. "medium" er markant bedre til dansk end
# "small" (bedre INPUT til parseren). "large-v3" er bedst men langsom/tung på
# CPU — sæt WHISPER_MODEL derefter hvis maskinen kan følge med.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

# Telegram-parsing: er modellens (justerede) confidence under denne grænse,
# bekræftes beskeden med knapper (✅/🔄/🗑) FØR den oprettes, i stedet for
# straks-eksekvering. Sæt til 0 for altid straks-eksekvering (gammel adfærd).
PARSE_CONFIRM_THRESHOLD = float(os.getenv("PARSE_CONFIRM_THRESHOLD", "0.75"))
# Små modeller er ofte for skråsikre på "event" (en dato ⇒ kalender). Vi
# trækker denne værdi fra confidence for event-gæt, så de oftere bekræftes.
EVENT_CONFIDENCE_PENALTY = float(os.getenv("EVENT_CONFIDENCE_PENALTY", "0.1"))
# Opt-in: route pass 1 til GPU-32b'eren når den er online (bedre præcision
# med det samme), med fallback til den lokale 7b. Default fra, fordi 32b'eren
# har keep_alive=0 og betaler kold opstart pr. kald → langsommere svar.
PARSE_PREFER_GPU = os.getenv("PARSE_PREFER_GPU", "false").lower() == "true"

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

# ── Gmail / Aula-indlæsning (Del 3) ─────────────────────────────────
# GMAIL_ENABLED=false slår hele pipelinen fra: intet poll-job, ingen kald.
GMAIL_ENABLED = os.getenv("GMAIL_ENABLED", "false").lower() == "true"
GMAIL_LABEL = os.getenv("GMAIL_LABEL", "Aula")
GMAIL_POLL_MINUTES = int(os.getenv("GMAIL_POLL_MINUTES", "10"))
GMAIL_MAX_PER_POLL = int(os.getenv("GMAIL_MAX_PER_POLL", "10"))
GMAIL_LOOKBACK_DAYS = int(os.getenv("GMAIL_LOOKBACK_DAYS", "7"))

AULA_MAX_BODY_CHARS = int(os.getenv("AULA_MAX_BODY_CHARS", "4000"))
AULA_SENDER_ALLOWLIST = _list("AULA_SENDER_ALLOWLIST") or ["aula.dk"]
AULA_MAX_ITEMS_PER_MAIL = int(os.getenv("AULA_MAX_ITEMS_PER_MAIL", "5"))

# Hybrid auto-mode: deterministisk gating (aula._auto_gates) bærer sikkerheden.
AULA_AUTO_ENABLED = os.getenv("AULA_AUTO_ENABLED", "false").lower() == "true"
AULA_AUTO_INTENTS = set(_list("AULA_AUTO_INTENTS") or ["event"])
AULA_AUTO_MIN_CONFIDENCE = float(os.getenv("AULA_AUTO_MIN_CONFIDENCE", "0.85"))
AULA_AUTO_MAX_DAYS_AHEAD = int(os.getenv("AULA_AUTO_MAX_DAYS_AHEAD", "90"))

AULA_PROPOSAL_TTL_HOURS = int(os.getenv("AULA_PROPOSAL_TTL_HOURS", "72"))
AULA_URGENT_HOURS = int(os.getenv("AULA_URGENT_HOURS", "24"))

# ── Generel post-triage (Del 4): hele INBOX minus støj ──────────────
# Admin-only overalt (dashboard-gating som finance, Telegram kun til admin).
# Ingen auto-handlinger — kun highlights og forslag med knapper.
TRIAGE_ENABLED = os.getenv("TRIAGE_ENABLED", "false").lower() == "true"
TRIAGE_LOOKBACK_DAYS = int(os.getenv("TRIAGE_LOOKBACK_DAYS", "3"))

ADMIN_EMAILS = {e.lower() for e in _list("ADMIN_EMAILS")}
TZ = os.getenv("TZ", "Europe/Copenhagen")
LATITUDE = float(os.getenv("LATITUDE", "56.15"))
LONGITUDE = float(os.getenv("LONGITUDE", "10.21"))
ELPRIS_AREA = os.getenv("ELPRIS_AREA", "DK1")

# ── Madplan-integration (Fase 2, INTEGRATION_SPEC §3.3/§A5) ──────────
# Tom MADPLAN_URL (eller tomt token) slår ugeplan-feed'et helt fra:
# intet poll-arbejde, ingen kald, ingen madplan-blok på dashboardet.
MADPLAN_URL = os.getenv("MADPLAN_URL", "")
LIFEHUB_API_TOKEN = os.getenv("LIFEHUB_API_TOKEN", "")  # brain → madplan bearer
MADPLAN_POLL_MINUTES = int(os.getenv("MADPLAN_POLL_MINUTES", "10"))
MADPLAN_STALE_MINUTES = int(os.getenv("MADPLAN_STALE_MINUTES", "10"))

# Intern lager-proxy (Fase 3, §3.2): madplan → brain. Tomt token = lukket.
# "På lager" = Vikunja-indkøbstasks afsluttet inden for dette vindue.
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
INVENTORY_DONE_DAYS = int(os.getenv("INVENTORY_DONE_DAYS", "7"))

DB_PATH = os.getenv("DB_PATH", "./lifehub.db")
