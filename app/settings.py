import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GCP_CLIENT_ID")
CLIENT_SECRET = os.getenv("GCP_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GCP_REDIRECT_URI")
LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")

# print(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
