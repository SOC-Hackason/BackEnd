from email.mime.text import MIMEText
import base64, time
import asyncio, aiohttp
import textwrap


from app.utils.gpt import query_gpt3
from app.utils.asyncio import run_in_threadpool
from app.utils.ml import get_ml_results

from app.models import User_Weight

from app.routers.gmail import LABELS_CATEGORY, LABELS_IMPORTANCE

TOPIC_CATEGORY =  ["Appointment", "Promotion", "School", "Work"]

async def classificate_email(msg:str):
    msg["body"] = msg["body"][:500]
    prompt = textwrap.dedent(f"""
        Classificate the following email in Japanese. You have to classify the email into the following categories:
        {LABELS_CATEGORY}, {LABELS_IMPORTANCE}.
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

async def get_user_weight(userid, db):
    user_weight = db.query(User_Weight).filter(User_Weight.user_id == userid).first()
    if not user_weight:
        init_dic = {"Work": 0.25, "School": 0.25, "Appointment": 0.25, "Promotion": 0.25}
        large_binary = base64.b64encode(str(init_dic).encode())
        user_weight = User_Weight(user_id=userid, model_weight = large_binary)
        db.add(user_weight)
        await db.commit()
        user_weight = user_weight.model_weight
    else:
        user_weight = user_weight.model_weight
        user_weight = base64.b64decode(user_weight)
    return user_weight

async def set_user_weight(userid, weight, db):
    weight = base64.b64encode(str(weight).encode())
    user_weight = db.query(User_Weight).filter(User_Weight.user_id == userid).first()
    user_weight.model_weight = weight
    await db.commit()


        
async def classificate_with_ml(msg:str, preferences:dict = {"Work": 0.25, "School": 0.25, "Appointment": 0.25, "Promotion": 0.25}):
    ham_score, topic = await run_in_threadpool(get_ml_results, msg)
    if ham_score < 0.5:
        category = "SPAM"
    else:
        category = TOPIC_CATEGORY[topic.argmax()]
    
    importance_by_topic = ham_score * topic
    importance_by_preference = [importance_by_topic[i] * preferences[TOPIC_CATEGORY[i]] for i in range(4)]

    if sum(importance_by_preference) < 0.5:
        importance = "GARBAGE"
    elif sum(importance_by_preference) < 0.8:
        importance = "NORMAL"
    else:
        importance = "EMERGENCY"

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
    