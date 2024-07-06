from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, exception_handlers
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import and_

import base64
import uuid
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import policy
from email.parser import BytesParser

from asyncio import sleep, gather

import requests
from urllib.parse import quote_plus

from app.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, LINE_CHANNEL_TOKEN
from app.schemas import OAuth2Code, FreeMessage, MailMessages
from app.db import get_db, get_db_session
from app.models import User_Auth, User_Line, User_Mail
from app.utils.gmail import *
from app.utils.gpt import *

from app.routers.gmail import router, user_id_from_lineid, line_id_from_userid, service_from_lineid, service_from_userid

# ラベル
LABELS_CATEGORY = ["WORK/SCHOOL", "SHOPPING", "ADS"]
LABELS_IMPORTABCE = ["EMERGENCY", "NORMAL", "GARBAGE"]


@router.get("/emails/unread_title")
async def get_unread_title(service=Depends(service_from_lineid)):
    unread_messages = get_unread_message(service)
    msg_ids = [msg["id"] for msg in unread_messages["messages"]]
    titles = await get_title_from_ids(service, msg_ids)
    return {"message": titles, "msg_ids": msg_ids}

@router.get("/emails/reply")
async def reply_mail(msg_id: str, order=None, service=Depends(service_from_lineid)):
    response_body, to, subject, thread_id = await reply_to_message(service, msg_id, order)
    res  = await make_draft(service, to, subject, response_body, msg_id, thread_id)
    return {"message": "Draft created", "debug": res}


# メールを取得する
@router.get("/emails")
async def get_emails(msg_id: str, service=Depends(service_from_lineid)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    return {"from": message["from"], "to": message["to"], "subject": message["subject"], "message": message["body"]}

@router.get("/emails/api")
async def get_emails_api(msg_id: str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    
    # msgオブジェクトをデータベースから取得　msg_idが存在しない場合は新規作成
    msg = db.execute(select(User_Mail).filter(User_Mail.msg_id == msg_id)).scalar_one_or_none()
    # TODO:
    
    


    
@router.get("/labels/create")
async def _create_label(service=Depends(service_from_lineid)):
    create_label(service, LABELS_CATEGORY+LABELS_IMPORTABCE)
    return {"message": "Labels created"}