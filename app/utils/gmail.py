# util file for gmail api
from email.mime.text import MIMEText
import base64, time
import asyncio, aiohttp
import textwrap

import google.auth.transport.requests 

from app.utils.gpt import query_gpt3
from app.utils.asyncio import run_in_threadpool


async def make_draft(service, to, subject, body, reply_to_id, thread_id):
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    message["from"] = "me"
    message["In-Reply-To"] = reply_to_id
    message["References"] = reply_to_id
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body_ = {"message": {"raw": raw, "threadId": thread_id}}
    service.users().drafts().create(userId="me", body=body_).execute()
    return body

async def reply_to_message(service, msg_id, order="なるべく丁寧に返信してください。"):
    """
    get the message from the message id and reply to the message
    """
    # run get_message_from_id_sync in threadpool 
    if order is None:
        order = "なるべく丁寧に返信してください。"
    order = order[:100]
    message = await run_in_threadpool(get_message_from_id_sync, service, msg_id)
    thread_id = message["threadId"]
    message = parse_message(message)
    body = message["body"][:1000]
    to = message["from"]
    to_address = get_reply_to(message)
    subject = message["subject"]
    escape = lambda x: "{" + x + "}"
    prompt = textwrap.dedent(
        f"""Make a template to reply to the following message in the same language as the original message:
            Subject: {subject}
            From: {to}
            Message: {body}
            Your reply should only include the message body and follow the order: {order}.
            Here are two examples:
            - Subject: 提出書類の不備について
            - From: 田中太郎 (学生教務係)
            - Message: 申し訳ございませんが、提出書類に不備がありました。再提出をお願いいたします。
            - Order: なるべく丁寧に返信してください。
            And here is the reply:
            - Reply: 学生教務係の田中太郎様、ご連絡ありがとうございます。お世話になっております{escape("名前")}です。お手数をおかけいたしますが、{escape("日付")}ごろに再提出させていただきます。
            ---
            - Subject: お問い合わせ
            - From: 田中太郎
            - Message: 何何の商品について詳しく教えてください。
            - Order: なるべく丁寧に返信してください。
            And here is the reply:
            - Reply: 田中様、お問い合わせありがとうございます。商品について詳しくお伝えいたします。{escape("商品名")}は{escape("説明")}です。{escape("価格")}円で販売しております。ご購入をご検討いただければ幸いです。
                     カタログを添付いたしますので、ご確認ください。何かご不明点がございましたら、お気軽にお問い合わせください。{escape("カタログ")}。
        """)
    response = await query_gpt3(prompt)
    print(response)
    return response, to_address, subject, thread_id
        

async def block_address_(service, address):
    """Block an email address\n
    Args:\n
    service: Gmail service object\n
    address: The email address to be blocked\n
    Returns:\n
    None\n
    """
    try:
        f = service.users().settings().filters().create(
            userId='me',
            body={
                "criteria": {
                    "from": address
                },
                "action": {
                    "removeLabelIds": ["INBOX"],
                    "addLabelIds": []
                }
            }
        )
        await run_in_threadpool(f.execute)
    except Exception as e:
        print(e)
        return None
    
async def unblock_address_(service, address):
    """Unblock an email address\n
    Args:\n
    service: Gmail service object\n
    address: The email address to be unblocked\n
    Returns:\n
    None\n
    """
    try:
        f = service.users().settings().filters().delete(
            userId='me',
            id=address
        )
        await run_in_threadpool(f.execute)
    except Exception as e:
        print(e)
        return None
    
async def get_recent_addresses_(service, max_results=10):
    """Get the received emails's address\n
    Args:\n
    service: Gmail service object\n
    Returns:\n
    addresses: List of recent addresses\n
    """
    try:
        f = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=max_results
        ).execute
        message_ids = await run_in_threadpool(f)
        tasks = [get_message_from_id_(service, message_id["id"]) for message_id in message_ids["messages"]]
        messages = await asyncio.gather(*tasks)
        parsed_messages = [parse_message(message) for message in messages]
        addresses = [parsed_message["from"] for parsed_message in parsed_messages]
        return list(set(addresses))
    except Exception as e:
        print(e)
        return None


def create_label(service, label_names):
    """Create a label in gmail account if it does not already exist\n
    Args:\n
    service: Gmail service object\n
    label_name: Name of the label to be created\n
    Returns:\n
    label: The created label object\n
    """
    try:
        for label_name in label_names:
            try:
                label = service.users().labels().create(
                    userId='me',
                    body={
                        'name': label_name,
                        'messageListVisibility': 'show',
                        'labelListVisibility': 'labelShow'
                    }
                ).execute()
            except Exception as e:
                print(e)
    except Exception as e:
        print(e)
        return None
    
def get_label_id(service, label_name):
    """Get the id of a label\n
    Args:\n
    service: Gmail service object\n
    label_name: The name of the label whose id is to be fetched\n
    Returns:\n
    label_id: The id of the label\n
    """
    try:
        labels = service.users().labels().list(userId='me').execute()
        for label in labels['labels']:
            if label['name'] == label_name:
                return label['id']
    except Exception as e:
        return None
    
# lableを付与する
def add_label(service, msg_id, label_id):
    """Add a label to a message\n
    Args:\n
    service: Gmail service object\n
    msg_id: The id of the message to which the label is to be added\n
    label_id: The id of the label to be added\n
    Returns:\n
    None\n"""
    try:
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={
                'addLabelIds': [label_id]
            }
        ).execute()
    except Exception as e:
        return None
    

async def remove_all_labels(service, msg_id):
    """Remove all labels from a message\n
    Args:\n
    service: Gmail service object\n
    msg_id: The id of the message from which all labels are to be removed\n
    Returns:\n
    None\n"""
    try:
        msg_label_ids = service.users().messages().get(userId='me', id=msg_id).execute()['labelIds']
        # extract user labels
        msg_label_ids = [label_id for label_id in msg_label_ids if label_id.startswith("Label_")]
        f = service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={
                'removeLabelIds': msg_label_ids
            }
        ).execute
        await run_in_threadpool(f)
        return "success" + str(msg_label_ids) 
    except Exception as e:
        return str(e)
    
def add_label_from_name(service, msg_id, label_name):
    """Add a label to a message\n
    Args:\n
    service: Gmail service object\n
    msg_id: The id of the message to which the label is to be added\n
    label_name: The name of the label to be added\n
    Returns:\n
    None\n"""
    try:
        label_id = get_label_id(service, label_name)
        add_label(service, msg_id, label_id)
    except Exception as e:
        return None
    
def get_unread_message(service, max_results=25):
    """Get all unread messages in the inbox\n
    Args:\n
    service: Gmail service object\n
    Returns:\n
    messages: List of unread messages' id\n
    """
    try:
        messages = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=max_results
        ).execute()
        return messages
    except Exception as e:
        print(e)
        return None

def get_all_message_ids(service, next_page_token=None):
    """Get all messages in the inbox\n
    Args:\n
    service: Gmail service object\n
    Returns:\n
    messages: List of messages' id\n
    """
    try:
        if next_page_token:
            messages = service.users().messages().list(userId='me', pageToken=next_page_token).execute()
        else:
            messages = service.users().messages().list(userId='me').execute()
        ids = [message['id'] for message in messages['messages']]
        return ids, messages.get("nextPageToken")
    except Exception as e:
        print(e)
        return None, None

async def get_message_from_id(service, msg_ids:list):
    """Get a message from its id\n
    Args:\n
    service: Gmail service object\n
    msg_id: The ids of the message to be fetched\n
    Returns:\n
    message: The fetched messages\n
    """
    tasks = [get_message_from_id_(service, msg_id) for msg_id in msg_ids]
    messages = await asyncio.gather(*tasks)
    return messages
    
async def get_title_from_ids(service, msg_ids:list):
    """Get the title of a message from its id\n
    Args:\n
    service: Gmail service object\n
    msg_id: The ids of the message whose title is to be fetched\n
    Returns:\n
    titles: The titles of the messages\n
    """
    messages = await get_message_from_id(service, msg_ids)
    titles = [parse_message(message)["subject"] for message in messages]
    return titles

async def get_message_from_id_async(service, msg_id):
    try:
        message = await run_in_threadpool(get_message_from_id_sync, service, msg_id)
        return message
    except Exception as e:
        print(e)
        return None

def get_message_from_id_sync(service, msg_id):
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format="raw").execute()
        return message
    except Exception as e:
        print(e)
        return str(e)

async def get_message_from_id_(service, msg_id, format="raw"):
    try:
        # アクセストークンを取得
        creds = service._http.credentials

        url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format={format}'
        headers = {
            'Authorization': f'Bearer {creds.token}'
        }

        async with aiohttp.ClientSession() as session:
            message = await fetch_message(session, url, headers)
            return message
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    
async def fetch_message(session, url, headers):
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        else:
            
            txt = await response.text()
            print(f"Failed to fetch message: {txt}")
            return None


def send_gmail_message(service, to, subject, body):
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw}
    message = service.users().messages().send(userId="me", body=body).execute()
    return message


async def mark_as_read(service, msg_id):
    """Mark a message as read\n
    Args:\n
    service: Gmail service object\n
    msg_id: The id of the message to be marked as read\n
    Returns:\n
    None\n
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={
                'removeLabelIds': ['UNREAD']
            }
        ).execute()
    except Exception as e:
        print(e)
        return None
    
    
async def classify_order(sentence: str):
    class_names = ["summary", "read", "greeting", "the other"]
    prompt = textwrap.dedent(f"""\
    Classify the following sentence into one of the following categories: {",".join(class_names)}. You must return just one category and must not contain any other information. 
    Exapmle: 
    1. - Sentences: 未読メールを要約して, ようやくして, まとめて, 要約してくれめんす。
    - Category: summary
    2. - Sentence: 既読にして, 全部読んだ, 了解, 把握した
     - Category: read 
    3. - Sentence: おはよう, ばいばい, ありがとう, やあ, こんにちは
     - Category: greeting
    4. - Sentence: うるさい, はいはい, いやいや, ajdaf, どうにかして
     - Category: the other. 
    では頑張ってください。
    Sentence: {sentence}""")
    print(prompt)
    response = await query_gpt3(prompt)
    return response

from email.parser import BytesParser
from email import policy
import email
import re

def parse_message(message):
    """
    from:
    to:
    subject:
    date:
    body:
    """
    # メッセージのペイロードを取得
     # メッセージをデコード
    msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
    mime_msg = email.message_from_bytes(msg_str)
    headers = {}
    body = ""

    # ヘッダー情報を取得
    for header in ['From', 'To', 'Subject', 'Date']:
        headers[header] = mime_msg[header]
        if headers[header]:
            # ヘッダーをデコード
            headers[header] = email.header.make_header(email.header.decode_header(headers[header]))
            headers[header] = str(headers[header])

    # メッセージの本文とファイルを取得
    if mime_msg.is_multipart():
        for part in mime_msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == 'text/plain' and 'attachment' not in content_disposition:
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                # 改行を統一
                body = body.replace('\r\n', '')
            elif content_type == 'text/html' and 'attachment' not in content_disposition and not body:
                # プレーンテキストが無い場合はHTMLを使用
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                # 改行を統一
                body = body.replace('\r\n', '')

    else:
        body = mime_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        # 改行を統一
        body = body.replace('\r\n', '')

    body = re.sub(r'[\t\n\r]+', '', body)


    return {
        "from": headers.get("From"),
        "to": headers.get("To"),
        "subject": headers.get("Subject"),
        "date": headers.get("Date"),
        "body": body,
    }

def get_reply_to(parsed_email):
    from_field = parsed_email["from"]
    
    # メールアドレスを抽出する正規表現パターン
    email_pattern = r'[\w\.-]+@[\w\.-]+'
    
    # from_fieldからメールアドレスを抽出
    match = re.search(email_pattern, from_field)
    
    if match:
        return match.group(0)
    else:
        # メールアドレスが見つからない場合は元のfromフィールドをそのまま返す
        return from_field


