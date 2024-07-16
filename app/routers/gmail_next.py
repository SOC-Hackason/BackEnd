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

import os
import pickle
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

#
labeled_msg_ids = set()
if os.path.exists("app/labeled_msg_ids.txt"):
    with open("app/labeled_msg_ids.txt", "rb") as f:
        labeled_msg_ids = pickle.load(f)
#
msg_labels_importance = {}
msg_labels_content = {}


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

@router.get("/change_label")
async def get_emails_ml(msg_id: str, line_id:str, label_type:str, label:int, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    user_id = await user_id_from_lineid(line_id, db)
    msg = await get_message_from_id_async(service, msg_id)
    msg = parse_message(msg)
    msg = msg["body"][:1000]

    if label_type == "importance":
        await add_label_from_name(service, msg_id, LABELS_IMPORTANCE[label])
        user_weight = await get_user_weight(user_id)
        topic_vector = await run_in_threadpool(get_ml_results, msg)
        importance_by_preference = [topic_vector[i] * user_weight[TOPIC_CATEGORY[i]] for i in range(4)]
        now_importance = sum(importance_by_preference)
        if label == 0:
            af_importance = 0.25
        elif label == 1:
            af_importance = 0.7
        else:
            af_importance = 0.9
        # パーセプトロンみたいな更新
        for i in range(4):
            user_weight[TOPIC_CATEGORY[i]] += 0.1 * (af_importance - now_importance) * topic_vector[i]
        await set_user_weight(user_id, user_weight, db)
    else:
        label = LABELS_CATEGORY[label]
        await add_label_from_name(service, msg_id, label)
        with open("app/labels_content.txt", "a") as f:
            f.write(f"{msg_id}, {msg}, {label}\n")
    
@router.get("/emails_dev")
async def get_emails_dev(line_id:str, msg_id:str=None, service=Depends(service_from_lineid), db: Session = Depends(get_db_session)):
    if msg_id is not None:
        if (line_id, msg_id) not in labeled_msg_ids:
            labeled_msg_ids.add((line_id, msg_id))
            msg_obj = await db.execute(select(User_Mail).filter(User_Mail.mail_id == msg_id))
            msg_obj = msg_obj.scalars().first()
            msg = await get_message_from_id_async(service, msg_id)
            msg = parse_message(msg)
            msg = msg["body"][:500]
            msg_labels_content[msg_id] = msg_obj.label_content
            msg_labels_importance[msg_id] = msg_obj.label_name
            with open("app/labels_importance.txt", "a") as f:
                f.write(f"{msg_id}, {msg}, {msg_obj.label_name}\n")
            with open("app/labels_content.txt", "a") as f:
                f.write(f"{msg_id}, {msg}, {msg_obj.label_content}\n")
            # save labeled_msg_ids to a file
            with open("app/labeled_msg_ids.txt", "wb") as f:
                pickle.dump(labeled_msg_ids, f)
    while True:
        msg_ids, next_page_token = get_all_message_ids(service)
        for msg_id in msg_ids:
            if (line_id, msg_id) in labeled_msg_ids:
                continue
            msg, _from, _to, _subject = await get_emails_summary_importance(msg_id, line_id, service, db)
            return {"from": _from, "to": _to, "subject": _subject, "message": msg.summary, "category": msg.label_content, "importance": msg.label_name, "id": msg_id}
        if not next_page_token:
            return {"message": "No more messages"}
        
@router.get("/emails_devl")
async def update_emails_label(line_id:str, label:int, message_id:str, label_type:str, service=Depends(service_from_lineid)):
    new_label = label
    labeled_msg_ids.add((line_id, message_id))
    msg = await get_message_from_id_async(service, message_id)
    msg = parse_message(msg)
    msg = msg["body"]
    if label_type == "importance":
        new_label = LABELS_IMPORTANCE[new_label]
        msg_labels_importance[message_id] = new_label
        with open("app/labels_importance.txt", "a") as f:
            f.write(f"{message_id}, {msg}, {new_label}\n")
    else:
        new_label = LABELS_CATEGORY[new_label]
        msg_labels_content[message_id] = new_label
        with open("app/labels_content.txt", "a") as f:
            f.write(f"{message_id}, {msg}, {new_label}\n")
            
    with open("app/labeled_msg_ids.txt", "wb") as f:
        pickle.dump(labeled_msg_ids, f)
    
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
