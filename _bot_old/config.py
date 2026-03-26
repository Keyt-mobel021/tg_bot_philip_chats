import os
from dotenv import load_dotenv

load_dotenv('.env')

TOKEN = os.getenv("TOKEN_TELEGA", "YOUR_BOT_TOKEN")

# ID администраторов (список Telegram ID)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Количество элементов на странице
PAGE_SIZE = 20
