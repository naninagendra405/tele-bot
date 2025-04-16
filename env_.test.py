import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("BOT_TOKEN")
print(f"BOT_TOKEN from .env: {token}")
