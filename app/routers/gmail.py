from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, exception_handlers, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as RequestGoogle

from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import and_

import base64
import uuid
import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import policy
from email.parser import BytesParser

from asyncio import sleep, gather
import asyncio

import requests
from urllib.parse import quote_plus
from typing import List

from app.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, LINE_CHANNEL_TOKEN
from app.schemas import OAuth2Code, FreeMessage, MailMessages
from app.db import get_db, get_db_session
from app.models import User_Auth, User_Line, User_Mail
from app.utils.gmail import *
from app.utils.gpt import *
from app.utils.linebot import list_message

router = APIRouter()


# OAuth2PasswordBearerは、OAuth 2.0トークンを取得するための依存関係を提供します。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# クライアントIDとクライアントシークレットの設定
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
SCOPES = ["https://mail.google.com/", "openid",  "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/gmail.settings.sharing", "https://www.googleapis.com/auth/gmail.settings.basic", "https://www.googleapis.com/auth/gmail.settings.basic"]

# メールの通知時間のデフォルト値
DEFAULT_DATE_TIME = datetime.time(15, 40, 0)
# 定期実行用のスケジューラを作成
scheduler = AsyncIOScheduler()
scheduler.start()
# 東京のタイムゾーンを設定
japan_tz = pytz.timezone('Asia/Tokyo')

# ラベル
LABELS_CATEGORY = ["WORK", "SCHOOL", "APPOINTMENT", "PROMOTIONS", "OTHER"]
LABELS_IMPORTANCE = ["EMERGENCY", "NORMAL", "GARBAGE"]
LEARNING_RATE = 0.05

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

async def user_id_from_lineid(line_id: str, db=Depends(get_db)):
    query = select(User_Line).where(User_Line.line_id == line_id)
    result = await db.execute(query)
    user_line = result.scalars().first()
    if not user_line:
        return {"message": "User not found"}
    return user_line.id

async def line_id_from_userid(user_id: int, db=Depends(get_db)):
    query = select(User_Line).where(User_Line.id == user_id)
    result = await db.execute(query)
    user_line = result.scalars().first()
    if not user_line:
        return {"message": "User not found"}
    return user_line.line_id


async def service_from_userid(user_id: str, db:Session=Depends(get_db)):
    query = select(User_Auth).where(User_Auth.id == user_id)
    result = await db.execute(query)
    user_auth = result.scalars().first()
    try:
        credentials = Credentials(
        token=user_auth.access_token,
        refresh_token=user_auth.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
        )
        if credentials.expired:
            credentials.refresh(RequestGoogle())
            print("refreshed--------------")
            user_auth.access_token = credentials.token
            await db.commit()
        service = build("gmail", "v1", credentials=credentials)
        return service
    # 来ないでしょ
    except Exception as e:
        print(e)
        return None

async def service_from_lineid(line_id: str, db=Depends(get_db)):
    user_id = await user_id_from_lineid(line_id, db)
    if not user_id:
        return None
    service = await service_from_userid(user_id, db)
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
        include_granted_scopes="true",
        prompt = "consent",
    )
    # clientidをcookieに保存する
    request.session["clientid"] = clientid
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def callback(backgroud_tasks: BackgroundTasks, request: Request, code: str = None, flow: Flow = Depends(get_oauth2_flow), db: Session = Depends(get_db)):
    if code:   
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
            client_id = request.session.get("clientid")
            if client_id is None:
                raise Exception("probably secret mode")
            
            # create Labels
            service = build("gmail", "v1", credentials=credentials)
            create_label(service, LABELS_CATEGORY+LABELS_IMPORTANCE)
            
            # check if the client_id is already registered or not
            query = select(User_Line).where(User_Line.line_id == client_id)
            result = await db.execute(query)
            user_line = result.scalars().first()
            if user_line:
                # 既に登録されている場合
                user_id = await user_id_from_lineid(client_id, db)
                trigger = CronTrigger(hour = DEFAULT_DATE_TIME.hour, minute = DEFAULT_DATE_TIME.minute, timezone=japan_tz)
                scheduler.add_job(notify_mail, trigger, args=[user_id], id=str(user_id), replace_existing=True)

                user_auth = User_Auth(id=user_id, refresh_token=credentials.refresh_token, access_token=credentials.token)
                await upsert_user_auth(user_auth, db)
                await db.commit()
                return RedirectResponse("line://ti/p/@805iiwyk")

            mail_address = get_email_address(credentials.token)
            user_auth = User_Auth(email=mail_address, refresh_token=credentials.refresh_token, access_token=credentials.token, notify_time=DEFAULT_DATE_TIME)
            await upsert_user_auth(user_auth, db)
            await db.commit()
            user_id = user_auth.id
            user_line = User_Line(id=user_id, line_id=client_id)
            db.add(user_line)
            await db.flush()
            
            # 決まった時間にメールをチェックするようにする
            trigger = CronTrigger(hour = DEFAULT_DATE_TIME.hour, minute = DEFAULT_DATE_TIME.minute)
            scheduler.add_job(notify_mail, trigger, args=[user_id], id=str(user_id), replace_existing=True)

            # 定期的にメールをチェックするようにする
            backgroud_tasks.add_task(check_mail, user_id, db)

            # 結果をコミット
            await db.commit()
            return RedirectResponse("line://ti/p/@805iiwyk")
        except Exception as e:
            print(e)
            await db.rollback()
            return RedirectResponse("line://ti/p/@805iiwyk")
        
    return {"message": "Code is required"}



# 要約の取得
@router.get("/emails/summary")
async def get_emails_summary(line_id, service=Depends(service_from_lineid), db=Depends(get_db)):

    user_id = await user_id_from_lineid(line_id, db)
    unread_message = get_unread_message(service)
    if unread_message is None:
        return {"message": "再認証してみてください。"}
    if unread_message['resultSizeEstimate'] == 0:
        return {"message": ["no new mail"]}
    # 25件まで取得
    msg_ids = [msg["id"] for msg in unread_message["messages"]]
    msg_ids = msg_ids[:12]
    # message の　パース
    # start summarise
    tasks = [summarise_email_(service, msg_id, db) for msg_id in msg_ids]
    summaries = await gather(*tasks)
    # upsert to db
    user_mails = [User_Mail(id=user_id, mail_id=msg_id, is_read=False, summary=summary) for msg_id, summary in zip(msg_ids, summaries)]
    tasks = [upsert_mails_to_user_mail(user_mail, db) for user_mail in user_mails]
    await gather(*tasks)
    await db.commit()
    #urls = [f"https://mail.google.com/mail/u/{0}/#inbox/{msg_id}" for msg_id in msg_ids]
    return {"message": summaries, "msg_ids": msg_ids}

@router.get("/emails/read")
async def read_emails(line_id, service=Depends(service_from_lineid), db=Depends(get_db)):
    """サマリーで送ったものをすべて既読にする"""
    # usermailのis_readがFのもののidを取得
    # それを既読にする
    user_id = await user_id_from_lineid(line_id, db)
    query = select(User_Mail).where(and_(User_Mail.id == user_id, User_Mail.is_read == False))
    result = await db.execute(query)
    user_mails = result.scalars().all()
    tasks = [mark_as_read(service, user_mail.mail_id) for user_mail in user_mails]
    await gather(*tasks)
    return {"message":"All mails are read"}

@router.get("/read")
async def read_mail(msg_ids: List[str]=Query(None), service=Depends(service_from_lineid)):
    tasks = [mark_as_read(service, msg_id) for msg_id in msg_ids]
    await gather(*tasks)
    return {"message": "All mails are read"}


@router.get("/change_time/")
async def change_time(line_id: str, hour: str, minute: str , db: Session = Depends(get_db)):
    """
    change notify time
    """
    user_id =  await user_id_from_lineid(line_id, db)
    if not user_id:
        raise HTTPException(status_code=400, detail="User not found")
    query = select(User_Auth).where(User_Auth.id == user_id)
    result = await db.execute(query)
    user_auth = result.scalars().first()
    user_auth.notify_time = datetime.time(int(hour), int(minute), 0)
    await db.commit()
    # update scheduler
    job = scheduler.get_job(str(user_id))
    if job:
        job.reschedule(CronTrigger(hour = int(hour), minute = int(minute), timezone=japan_tz))
    else:
        trigger = CronTrigger(hour = int(hour), minute = int(minute), timezone=japan_tz)
        scheduler.add_job(notify_mail, trigger, args=[user_id], id=str(user_id), replace_existing=True)
    return {"message": "Time changed successfully"}

@router.post("/free_sentence")
async def free_sentence(request: FreeMessage, service=Depends(service_from_lineid), db=Depends(get_db)):
    sentence = request.sentence
    line_id = request.line_id
    order = await classify_order(sentence)
    if "summary" in order:
        res = await get_emails_summary(line_id, service, db)
        res["res"] = "summary"
        return res
    elif "read" in order:
        res = await read_emails(line_id, service, db)
        res["res"] = "read"
        return res
    elif "greeting" in order:
        return {"message": sentence}
    else:
        return {"message": "cant understand your message."}

async def notify_mail(user_id: int):
    line_id = None
    service = None
    async for db in get_db():
        line_id = await line_id_from_userid(user_id, db)
        service = await service_from_userid(user_id, db)
    messages = await list_message(service)
    print(LINE_CHANNEL_TOKEN)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_TOKEN}'
    }
    payload = {
        'to': line_id,  # LINEユーザーIDを指定
        'messages': messages
    }
    response = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
    if response.status_code == 200:
        print('Message sent successfully')
    else:
        print(f'Failed to send message: {response.status_code}, {response.text}')


async def check_mail(user_id: int, db):
    service = await service_from_userid(user_id, db)
    while True:
        unread_ids = get_unread_message(service)
        for id in unread_ids:
            # if the mail is already read, skip
            # システムが過去にメールを見ていないならば
            user_mail = User_Mail(id=user_id, mail_id=id, is_read=False)
            try:
                db.add(user_mail)
                await db.commit()
            except Exception as e:
                await db.rollback()
                continue

            msg = service.users().messages().get(userId="me", id=id, format='raw').execute()
            mail = parse_message(msg)

            # send line message
            # get line id
            line_id = await line_id_from_userid(user_id, db)
            if False:
                send_line_message(LINE_CHANNEL_TOKEN, line_id, f"New mail from {mail['from']}: {mail['subject']}")
                user_mail.is_read = True
                await db.commit()
        await sleep(3600)



def send_line_message(line_token, user_id, message):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {line_token}'
    }
    payload = {
        'to': user_id,  # LINEユーザーIDを指定
        'messages': [{'type': 'text', 'text': message}]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print('Message sent successfully')
    else:
        print(f'Failed to send message: {response.status_code}, {response.text}')

def get_email_address(token: str):
    headers = {"Authorization":
        f"Bearer {token}"}
    response = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers=headers)
    return response.json().get("email")

async def upsert_mails_to_user_mail(user_mail: User_Mail, db: Session):
    """
    add user_mail to db if not exists
    update user_mail if exists
    """
    query = select(User_Mail).where(and_(User_Mail.id == user_mail.id, User_Mail.mail_id == user_mail.mail_id))
    result = await db.execute(query)
    bef_user_mail = result.scalars().first()
    if not bef_user_mail:
        db.add(user_mail)
    else:
        bef_user_mail.is_read = user_mail.is_read
        bef_user_mail.summary = user_mail.summary
        bef_user_mail.label_content = user_mail.label_content
        bef_user_mail.label_name = user_mail.label_name

async def upsert_user_auth(user_auth: User_Auth, db: Session):
    """
    add user_auth to db if not exists
    update user_auth if exists
    """
    query = select(User_Auth).where(User_Auth.id == user_auth.id)
    result = await db.execute(query)
    bef_user_auth = result.scalars().first()
    if not bef_user_auth:
        db.add(user_auth)
    else:
        bef_user_auth.refresh_token = user_auth.refresh_token
        bef_user_auth.access_token = user_auth.access_token
            
async def summarise_email_(service, msg_id, db,  is_read=True):
    # if the email is already summarised, return the summary
    query = select(User_Mail).where(User_Mail.mail_id == msg_id)
    result = await db.execute(query)
    user_mail = result.scalars().first()
    if user_mail and user_mail.summary:
        return user_mail.summary
    else:
        email_content = await get_message_from_id_(service, msg_id)
        parsed_message = parse_message(email_content)
        parsed_message["body"] = parsed_message["body"][:500]
        summary = await summarise_email(parsed_message)
        return summary
        