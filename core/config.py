import os
from dotenv import load_dotenv

load_dotenv()

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRIES = ["gb", "de", "nl", "fr", "us"]

REMOTEOK_API_URL = "https://remoteok.com/api"
