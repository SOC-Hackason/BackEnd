from email import policy
from email.parser import BytesParser
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

from sqlalchemy.orm import Session
from sqlalchemy.future import select

import base64
import uuid

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from urllib.parse import quote_plus

from app.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
from app.schemas import OAuth2Code
from app.db import get_db
from app.models import User_Auth, User_Line

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

async def service_from_lineid(line_id: str, db=Depends(get_db)):
    query = select(User_Line).where(User_Line.line_id == line_id)
    result = await db.execute(query)
    user_line = result.scalars().first()
    if not user_line:
        return {"message": "User not found"}
    
    query = select(User_Auth).where(User_Auth.id == user_line.id)
    result = await db.execute(query)
    user_auth = result.scalars().first()

    credentials = Credentials(user_auth.access_token)
    service = build("gmail", "v1", credentials=credentials)
    return service



# フロントエンドからのリクエストを受け取り、OAuth2の認証フローを開始する
@router.post("/code")
async def code(code: OAuth2Code, flow: Flow = Depends(get_oauth2_flow)):
    code = code.code
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    #FIXed エラーの解決　フロントエンドのリダイレクト先と一致しなかったため？
    flow.redirect_uri = "http://localhost:3000"
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return {"token": credentials.token, "refresh_token": credentials.refresh_token, "token_uri": TOKEN_URI}

# ここを使う
@router.get("/auth")
async def auth(request: Request, flow: Flow = Depends(get_oauth2_flow), clientid: str = None):
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true"
    )
    # clientidをcookieに保存する
    request.session["clientid"] = clientid
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def callback(request: Request, code: str = None, flow: Flow = Depends(get_oauth2_flow), db: Session = Depends(get_db)):
    if code:   
        flow.fetch_token(code=code)
        credentials = flow.credentials
        mail_address = get_email_address(credentials.token)
        user_auth = User_Auth(email=mail_address, refresh_token=credentials.refresh_token, access_token=credentials.token)

        try:
            db.add(user_auth)
            await db.flush()
            user_id = user_auth.id
            client_id = request.session.get("clientid")
            user_line = User_Line(id=user_id, line_id=client_id)
            db.add(user_line)
        except Exception as e:
            print(e)
            raise HTTPException(status_code=400, detail="Failed to add user_auth")
        
        await db.commit()

        return {"email":mail_address, "access_token":credentials.token, "refresh_token": credentials.refresh_token}
    return {"message": "Code is required"}

# メールを取得する
@router.get("/emails/{line_id}")
async def get_emails(mail_nums: int = 1, service=Depends(service_from_lineid)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    
    results = service.users().messages().list(userId="me").execute()
    messages = results.get("messages", [])
    res = []
    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"], format='raw').execute()
        res.append(parse_message(msg))
        if len(res) == mail_nums:
            break
    return res


# TODO 絶対消す
@router.get("/user_auth/all")
async def get_all_user_auth(db: Session = Depends(get_db)):
    query = select(User_Auth)
    result = await db.execute(query)
    tokens = result.scalars().all()
    return tokens


def get_email_address(token: str):
    headers = {"Authorization":
        f"Bearer {token}"}
    response = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
    return response.json().get("email")

def parse_message(message):
    # メッセージのペイロードを取得
    msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))

    # メッセージを解析
    msg = BytesParser(policy=policy.default).parsebytes(msg_str)

    # メッセージのヘッダーと本文を取得
    headers = dict(msg.items())
    body = ""
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode()
                #body = body.replace('\r\n', '\n') 
    else:
        body = msg.get_payload(decode=True).decode()
        #body = body.replace('\r\n', '\n') 

    return {
        "from": headers.get("From"),
        "to": headers.get("To"),
        "subject": headers.get("Subject"),
        "date": headers.get("Date"),
        "body": body
    }