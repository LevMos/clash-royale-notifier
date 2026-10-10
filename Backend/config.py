import os
from dotenv import load_dotenv

load_dotenv()

CR_TOKEN = os.getenv("CR_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

CR_PROXY_BASE = "https://proxy.royaleapi.dev/v1"
HTTP_TIMEOUT = 10

_missing = [
    name for name, value in {
        "TG_TOKEN": TG_TOKEN,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }.items() if not value
]
if _missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(_missing)}")