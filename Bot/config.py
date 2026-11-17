import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = os.getenv("TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000") # если не задается то так (это как локалхост). если задается (на сервере) то берем переменную от сервера