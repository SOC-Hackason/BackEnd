from email.mime.text import MIMEText
import base64, time
import asyncio, aiohttp
import textwrap


from app.utils.gpt import query_gpt3
from app.utils.asyncio import run_in_threadpool

from app.routers.gmail import LABELS_CATEGORY, LABELS_IMPORTABCE

async def classificate_email(msg:str):
    msg["body"] = msg["body"][:500]
    prompt = textwrap.dedent(f"""
        Classificate the following email in Japanese. You have to classify the email into the following categories:
        {LABELS_CATEGORY+["the others"]}, {LABELS_IMPORTABCE}.
        Your classification should be based on the content of the email. Here are some examples:
        - Email xx xx様 LINEヤフー株式会社 新卒採用担当です。 マイページへメッセージを送信しましたので ログインして内容をご確認下さい。
        - Reply "WORK/SHOOL, EMERGENCY"
        - Email こんにちは！サポーターズ運営事務局です。本日は、 技育CAMPアカデミアのご案内です。技育CAMPアカデミアでは、年間を通じて週1,2回のペースでオンライン技術勉強会を実施しています。
        - Reply "WORK/SHOOL, GARBAGE"
        Let's classify the following email:
        {msg}
        """)
    res = await query_gpt3(prompt)
    if "WORK/SCHOOL" in res:
        category = "WORK/SCHOOL"
    elif "SHOPPING" in res:
        category = "SHOPPING"
    elif "ADS" in res:
        category = "ADS"
    else:
        category = "the others"
    if "EMERGENCY" in res:
        importance = "EMERGENCY"
    elif "NORMAL" in res:
        importance = "NORMAL"
    elif "GARBAGE" in res:
        importance = "GARBAGE"
    else:
        importance = "NORMAL"
    
    
    return {"category": category, "importance": importance}
        
    