import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")

# Provider được chọn tự động: anthropic > groq
# Có thể ghi đè bằng AI_PROVIDER=groq hoặc AI_PROVIDER=anthropic
_provider_env = os.getenv("AI_PROVIDER", "").lower()
if _provider_env in ("anthropic", "groq"):
    AI_PROVIDER = _provider_env
elif ANTHROPIC_API_KEY:
    AI_PROVIDER = "anthropic"
elif GROQ_API_KEY:
    AI_PROVIDER = "groq"
else:
    AI_PROVIDER = "none"

TIKTOK_ACCESS_TOKEN  = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "")

_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: list[int] = [int(x) for x in _ids.split(",") if x.strip()]

DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "vi-VN-HoaiMyNeural")
DEFAULT_GENRE = os.getenv("DEFAULT_GENRE", "romance")

# Thư mục
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
WORK_DIR   = os.path.join(BASE_DIR, "work_dir")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(WORK_DIR,   exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_PATH = os.path.join(ASSETS_DIR, "font.ttf")
