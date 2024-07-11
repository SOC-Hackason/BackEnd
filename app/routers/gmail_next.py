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
from app.utils.label import *

from app.routers.gmail import router, user_id_from_lineid, line_id_from_userid, service_from_lineid, service_from_userid, summarise_email_, upsert_mails_to_user_mail
# ラベル
LABELS_CATEGORY = ["WORK/SCHOOL", "SHOPPING", "ADS"]
LABELS_IMPORTABCE = ["EMERGENCY", "NORMAL", "GARBAGE"]


@router.get("/unread_titles")
async def get_unread_title(max_results: int = 12, service=Depends(service_from_lineid)):
    unread_messages = get_unread_message(service)
    msg_ids = [msg["id"] for msg in unread_messages["messages"]]
    msg_ids = msg_ids[:max_results]
    titles = await get_title_from_ids(service, msg_ids)
    return {"message": titles, "msg_ids": msg_ids}

@router.get("/reply")
async def reply_mail(msg_id: str, order=None, service=Depends(service_from_lineid)):
    response_body, to, subject, thread_id = await reply_to_message(service, msg_id, order)
    body = await make_draft(service, to, subject, response_body, msg_id, thread_id)
    return {"message": body}

# メールを取得する
@router.get("/emails")
async def get_emails(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    msg, _from, _to, _subject = await get_emails_summary_importance(msg_id, line_id, service, db)
    return {"from": _from, "to": _to, "subject": _subject, "message": msg.summary, "category": msg.label_content, "importance": msg.label_name}

@router.get("/emails_ml")
async def get_emails_ml(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    msg, _from, _to, _subject = await get_emails_summary_importance_ml(msg_id, line_id, service, db)
    return {"from": _from, "to": _to, "subject": _subject, "message": msg.summary, "category": msg.label_content, "importance": msg.label_name}

@router.get("/emails/ids")
async def get_email_ids(service=Depends(service_from_lineid), next_page_token:str=None):
    ids, next_page_token = get_all_message_ids(service)
    return {"message": ids, "next_page_token": next_page_token}
    
@router.get("/vectorize")
async def vectorize_email_api(msg_id:str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    message["body"] = message["body"][:500]
    res = await vectorize_email(message)
    return {"vector": res, "message": message}
    
@router.get("/block_address")
async def block_address(line_id: str, address: str, service=Depends(service_from_lineid)):
    await block_address_(service, address)
    return {"message": "blocked"}

@router.get("/unblock_address")
async def unblock_address(address: str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    await unblock_address_(service, address)
    return {"message": "unblocked"}

@router.get("/recent_addresses")
async def get_recent_addresses(service=Depends(service_from_lineid)):
    addresses = await get_recent_addresses_(service)
    return {"message": addresses}



async def get_emails_summary_importance(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    
    user_id = await user_id_from_lineid(line_id, db)
    
    # msgオブジェクトをデータベースから取得　msg_idが存在しない場合は新規作成
    msg = await db.execute(select(User_Mail).filter(User_Mail.mail_id == msg_id))
    msg = msg.scalars().first()
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    message["body"] = message["body"][:700]
    _from = message["from"]
    _to = message["to"]
    _subject = message["subject"]
    
    if not msg:
        summary = await summarise_email(message)
        category, importance = await classificate_email(message)
        msg = User_Mail(mail_id = msg_id, id=user_id, is_read=True, summary= summary, label_content=category, label_name=importance)
        db.add(msg)
        await db.commit()
    else:
        if msg.label_content is None:
            category, importance = await classificate_email(message)
            msg.label_content = category
            msg.label_name = importance
        
        if msg.summary is None:
            msg.summary = await summarise_email(message)
        
        await db.commit()
        
    return msg, _from, _to, _subject

async def get_emails_summary_importance_ml(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    
    user_id = await user_id_from_lineid(line_id, db)
    
    # msgオブジェクトをデータベースから取得　msg_idが存在しない場合は新規作成
    msg = await db.execute(select(User_Mail).filter(User_Mail.mail_id == msg_id))
    msg = msg.scalars().first()
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    message["body"] = message["body"][:700]
    _from = message["from"]
    _to = message["to"]
    _subject = message["subject"]
    
    if not msg:
        summary = await summarise_email(message)
        category, importance = await classificate_with_ml(summary)
        msg = User_Mail(mail_id = msg_id, id=user_id, is_read=True, summary= summary, label_content=category, label_name=importance)
        db.add(msg)
        await db.commit()
    else:
        if msg.summary is None:
            msg.summary = await summarise_email(message)

        category, importance = await classificate_with_ml(msg.summary)
        msg.label_content = category
        msg.label_name = importance
        

        await db.commit()
        
    return msg, _from, _to, _subject