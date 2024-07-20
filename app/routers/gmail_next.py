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
from collections import defaultdict as ddict

import requests
from urllib.parse import quote_plus

from app.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, LINE_CHANNEL_TOKEN
from app.schemas import OAuth2Code, FreeMessage, MailMessages
from app.db import get_db, get_db
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

# cheating
user_language = ddict(lambda: "Japanese")
user_block_address = ddict(set)

@router.get("/unread_titles")
async def get_unread_title(background_tasks: BackgroundTasks, line_id:str, max_results: int = 12, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    unread_messages = get_unread_message(service)
    msg_ids = [msg["id"] for msg in unread_messages["messages"]]
    msg_ids = msg_ids[:max_results]
    titles = await get_title_from_ids(service, msg_ids)
    # classify
    for msg_id in msg_ids:
        asyncio.create_task(classify_email(msg_id, line_id, service))

    return {"message": titles, "msg_ids": msg_ids}

async def classify_email(msg_id, line_id, service):
    # db session
    async for db in get_db():
        msg, _from, _to, _subject = await get_emails_summary_importance(msg_id, line_id, service, db, is_summarise=False)
        await add_label_from_name_async(service, msg_id, msg.label_content)
        await add_label_from_name_async(service, msg_id, msg.label_name)

@router.get("/summary")
async def get_summary(line_id:str, max_results:int = 6, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    # get unread messages
    unread_messages = get_unread_message(service)
    msg_ids = [msg["id"] for msg in unread_messages["messages"]]
    msg_ids = msg_ids[:max_results]
    tasks = [get_message_from_id_async(service, msg_id) for msg_id in msg_ids]
    messages = await gather(*tasks)
    messages = [parse_message(msg) for msg in messages]
    messages = [msg["body"][:1500] for msg in messages]
    # get summary
    user_id = await user_id_from_lineid(line_id, db)
    language = user_language[user_id]
    tasks = [summarise_email(msg, language=language) for msg in messages]
    summaries = await gather(*tasks)
    # classify
    for msg_id in msg_ids:
        asyncio.create_task(classify_email(msg_id, line_id, service))

    
    return {"message": summaries, "msg_ids": msg_ids}




@router.get("/titles_importance")
async def get_unread_title_importance(line_id:str, importance:str, max_results: int = 12, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    # from db get message which have specified importance
    user_id = await user_id_from_lineid(line_id, db)
    query = select(User_Mail.mail_id).filter(and_(User_Mail.id == user_id, User_Mail.label_name == importance)).order_by(User_Mail.label_name.desc()).limit(max_results)
    messages = await db.execute(query)
    creds = service._http.credentials
    msg_ids = messages.scalars().all()
    titles = await get_title_from_ids(service, msg_ids)
    return {"message": titles, "msg_ids": msg_ids}

@router.get("/titles_content")
async def get_unread_title_content(line_id:str, content:str, max_results: int = 12, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    # from db get message which have specified content
    user_id = await user_id_from_lineid(line_id, db)
    query = select(User_Mail.mail_id).filter(and_(User_Mail.id == user_id, User_Mail.label_content == content)).order_by(User_Mail.label_content.desc()).limit(max_results)
    messages = await db.execute(query)
    msg_ids = messages.scalars().all()
    titles = await get_title_from_ids(service, msg_ids)
    return {"message": titles, "msg_ids": msg_ids}

@router.get("/reply")
async def reply_mail(msg_id: str, order=None, service=Depends(service_from_lineid)):
    response_body, to, subject, thread_id = await reply_to_message(service, msg_id, order)
    body = await make_draft(service, to, subject, response_body, msg_id, thread_id)
    return {"message": body}

# メールを取得する
@router.get("/emails")
async def get_emails(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    # activate service
    msg, _from, _to, _subject = await get_emails_summary_importance(msg_id, line_id, service, db)
    user_id = await user_id_from_lineid(line_id, db)
    return {"from": _from, "to": _to, "subject": _subject, "message": msg.summary, "category": msg.label_content, "importance": msg.label_name, "is_English": user_language[user_id] != "Japanese"}

@router.get("/emails_ml")
async def get_emails_ml(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    msg, _from, _to, _subject = await get_emails_summary_importance_ml(msg_id, line_id, service, db)
    return {"from": _from, "to": _to, "subject": _subject, "message": msg.summary, "category": msg.label_content, "importance": msg.label_name}

@router.get("/change_label")
async def get_emails_ml(msg_id: str, line_id:str, label_type:str, label:int, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    if not service:
        raise HTTPException(status_code=400, detail="Service is required")
    user_id = await user_id_from_lineid(line_id, db)
    msg = await get_message_from_id_async(service, msg_id)
    msg = parse_message(msg)
    msg = msg["body"][:1000]

    if label_type == "importance":
        # label
        await remove_all_labels(service, msg_id)
        add_label_from_name(service, msg_id, LABELS_IMPORTANCE[label])

        # update db
        msg_o = await db.execute(select(User_Mail).filter(User_Mail.mail_id == msg_id))
        msg_o = msg_o.scalars().first()
        msg_o.label_name = LABELS_IMPORTANCE[label]
        await db.commit()
        
        # update user_weight
        user_weight = await get_user_weight(user_id, db)
        topic_vector = await run_in_threadpool(get_ml_results, msg)
        importance_by_preference = [topic_vector[1][i] * user_weight[TOPIC_CATEGORY[i]] * topic_vector[0] for i in range(4)]
        now_importance = sum(importance_by_preference)
        af_importance = convert_label_index_to_importance(label)
        # パーセプトロンみたいな更新
        for i in range(4):
            user_weight[TOPIC_CATEGORY[i]] += 0.1 * (af_importance - now_importance) * topic_vector[1][i]
        await set_user_weight(user_id, user_weight, db)

    else:
        # label
        label = LABELS_CATEGORY[label]
        await remove_all_labels(service, msg_id)
        add_label_from_name(service, msg_id, label)
        # update db
        msg_o = await db.execute(select(User_Mail).filter(User_Mail.mail_id == msg_id))
        msg_o = msg_o.scalars().first()
        msg_o.label_content = label
        await db.commit()
        # save labeled_msg_ids to a file
        with open("app/labels_content.txt", "a") as f:
            f.write(f"{msg_id}, {msg}, {label}\n")
        
    return {"message": f"ラベルの変更に成功しました。"}
    
@router.get("/emails_dev")
async def get_emails_dev(line_id:str, msg_id:str=None, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
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

@router.get("/change_language")
async def change_language(line_id:str, language:str, db: Session = Depends(get_db)):
    user_id = await user_id_from_lineid(line_id, db)
    user_language[user_id] = language
    return {"message": "success"}
    
@router.get("/vectorize")
async def vectorize_email_api(msg_id:str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    message = await get_message_from_id_async(service, msg_id)
    message = parse_message(message)
    message["body"] = message["body"][:500]
    res = await vectorize_email(message)
    return {"vector": res, "message": message}
    
@router.get("/block_address")
async def block_address(line_id: str, address: str, addressname:str, service=Depends(service_from_lineid)):
    address_with_name = f"{addressname} <{address}>"
    user_block_address[line_id].add(address_with_name)
    await block_address_(service, address)
    return {"message": "blocked"}

@router.get("/unblock_address")
async def unblock_address(line_id:str, address: str, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    user_block_address[line_id].discard(address)
    await unblock_address_(service, address)
    return {"message": "unblocked"}

@router.get("/block_address_list")
async def block_address_list(line_id:str):
    return {"message": user_block_address[line_id]}

@router.get("/recent_addresses")
async def get_recent_addresses(service=Depends(service_from_lineid)):
    addresses = await get_recent_addresses_(service)
    return {"message": addresses}

async def get_emails_summary_importance(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db), is_summarise: bool = True):
    
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
    
    language = user_language[user_id]
    
    if msg is None:
        if is_summarise:
            summary = await summarise_email(message, language=language)
        else:
            summary = None
        category, importance = await classificate_email(message)
        msg = User_Mail(mail_id = msg_id, id=user_id, is_read=True, summary= summary, label_content=category, label_name=importance)
        db.add(msg)
        await db.commit()
    else:
        if msg.label_content is None:
            category, importance = await classificate_email(message)
            msg.label_content = category
            msg.label_name = importance
        
        if is_summarise:
            msg.summary = await summarise_email(message, language=language)
        
        await db.commit()
        
    return msg, _from, _to, _subject

async def get_emails_summary_importance_ml(msg_id: str, line_id:str, service=Depends(service_from_lineid), db: Session = Depends(get_db)):
    
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
    language = "English" if user_id in enlanguage_user else "Japanese"
    
    if not msg:
        summary = await summarise_email(message, language)
        category, importance = await classificate_with_ml(summary)
        msg = User_Mail(mail_id = msg_id, id=user_id, is_read=True, summary= summary, label_content=category, label_name=importance)
        db.add(msg)
        await db.commit()
    else:
        if msg.summary is None:
            msg.summary = await summarise_email(message, language)

        category, importance = await classificate_with_ml(msg.summary)
        msg.label_content = category
        msg.label_name = importance
        

        await db.commit()
        
    return msg, _from, _to, _subject
