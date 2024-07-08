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
        {LABELS_CATEGORY}, {LABELS_IMPORTABCE}.
        Your classification should be based on the content of the email. Here are some examples:
        - Email xx xx様 LINEヤフー株式会社 新卒採用担当です。 マイページへメッセージを送信しましたので ログインして内容をご確認下さい。
        - Reply "WORK, EMERGENCY"
        - Email こんにちは！サポーターズ運営事務局です。本日は、 技育CAMPアカデミアのご案内です。技育CAMPアカデミアでは、年間を通じて週1,2回のペースでオンライン技術勉強会を実施しています。
        - Reply "WORK, GARBAGE"
        - Email xx xx様 xx大学教務係です。xx xxさんの学生証が見つかりました。お手数ですが、教務係までお越しいただき、お受け取りください。
        - Reply "SCHOOL, EMERGENCY"
        - Email xx xx様 新商品の案内です。
        - Reply "ADS, GARBAGE"
        Let's classify the following email:
        {msg}
        """)
    res = await query_gpt3(prompt)
    if "WORK" in res:
        category = "WORK"
    elif "SCHOOL" in res:
        category = "SCHOOL"
    elif "APPOINTMENT" in res:
        category = "APPOINTMENT"
    elif "PROMOTIONS" in res:
        category = "PROMOTIONS"
    elif "SPAM" in res:
        category = "SPAM"
    else:
        category = "OTHER"
    if "EMERGENCY" in res:
        importance = "EMERGENCY"
    elif "NORMAL" in res:
        importance = "NORMAL"
    elif "GARBAGE" in res:
        importance = "GARBAGE"
    else:
        importance = "NORMAL"
    
    
    return category, importance
        
async def vectorize_email(msg:str):
    prompt = textwrap.dedent(f"""
        Vectorize the following email in Japanese. You have to vectorize the email based on the content of the email.
        Vectorize the email into a 4-dimensional vector. The vector should be a comma-separated string. Each dimension should be between 0 and 1. The sum of all dimensions don't have to be 1.
        The first dimension should represent the importance of the email in term of {LABELS_CATEGORY[0]}.
        The second dimension should represent the importance of the email in term of {LABELS_CATEGORY[1]}.
        The third dimension should represent the importance of the email in term of {LABELS_CATEGORY[2]}.
        The fourth dimension should represent the importance of the email in term of {LABELS_CATEGORY[3]}.
        Here is an example:
        - Email xx xx様 LINEヤフー株式会社 新卒採用担当です。 マイページへメッセージを送信しましたので ログインして内容をご確認下さい。
        - Vectorize "0.938232, 0.01, 0.3245, 0.03"
        - Email こんにちは！サポーターズ運営事務局です。本日は、 技育CAMPアカデミアのご案内です。技育CAMPアカデミアでは、年間を通じて週1,2回のペースでオンライン技術勉強会を実施しています。
        - Vectorize "0.523, 0.01, 0.23, 0.678"
        Let's vectorize the following email:
        {msg}
        """)
    res = await query_gpt3(prompt)
    return res
    