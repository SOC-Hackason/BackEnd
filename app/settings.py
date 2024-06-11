import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GCP_CLIENT_ID")
CLIENT_SECRET = os.getenv("GCP_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GCP_REDIRECT_URI")

# print(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
