from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from urllib.parse import quote_plus

from app.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
from app.schemas import OAuth2Code
from app.db import get_db
from sqlalchemy.orm import Session

router = APIRouter()

# OAuth2PasswordBearerは、OAuth 2.0トークンを取得するための依存関係を提供します。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# クライアントIDとクライアントシークレットの設定
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
SCOPES = ["https://mail.google.com/", "openid",  "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]

# OAuth2の認証フローを開始する
def get_oauth2_flow():
    return Flow.from_client_config(
        {
            "web":
            {
                "client_id":CLIENT_ID,
                "project_id":"secret-energy-425406-a3",
                "auth_uri":"https://accounts.google.com/o/oauth2/auth",
                "token_uri":"https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
                "client_secret":CLIENT_SECRET,
                "redirect_uris":["http://localhost","http://localhost:8000/gmail/callback"],
                "javascript_origins":["http://localhost","http://localhost:3000"]
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

# フロントエンドからのリクエストを受け取り、OAuth2の認証フローを開始する
@router.post("/code")
async def code(code: OAuth2Code, flow: Flow = Depends(get_oauth2_flow)):
    code = code.code
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    #FIXME redirect_uri_mismatchエラーが発生する。多分フロントエンドの問題
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return {"token": credentials.token, "refresh_token": credentials.refresh_token, "token_uri": TOKEN_URI}

# ここを使う
@router.get("/auth")
async def auth(flow: Flow = Depends(get_oauth2_flow)):
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def callback(flow: Flow = Depends(get_oauth2_flow), code: str = None, db: Session = Depends(get_db)):
    if code:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        # show email address
        headers = {"Authorization":
            f"Bearer {credentials.token}"}
        response = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
        #TODO dbにmailアドレスリフレッシュトークンを保存する
        return {"email":response.json().get("email"), "access_token":credentials.token, "refresh_token": credentials.refresh_token}
    return {"message": "Code is required"}
    
    
    



