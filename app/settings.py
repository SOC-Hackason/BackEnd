import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
GPT_TOKEN = os.getenv("GPT_TOKEN")

# print(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
