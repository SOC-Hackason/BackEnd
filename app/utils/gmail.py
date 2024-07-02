# util file for gmail api
from email.mime.text import MIMEText
import base64
import asyncio, aiohttp
import google.auth.transport.requests 
from app.utils.gpt import query_gpt3


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
                pass
    except Exception as e:
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
    tasks = [get_title_from_id_(service, msg_id) for msg_id in msg_ids]
    titles = await asyncio.gather(*tasks)
    return titles

async def get_title_from_id_(service, msg_id):
    try:
        # アクセストークンを取得
        creds = service._http.credentials

        url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata'
        headers = {
            'Authorization': f'Bearer {creds.token}'
        }

        async with aiohttp.ClientSession() as session:
            message = await fetch_message(session, url, headers)
            return message['payload']['headers'][1]['value']
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

async def get_message_from_id_(service, msg_id):
    try:
        # アクセストークンを取得
        creds = service._http.credentials

        url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=raw'
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
            print(f"Failed to fetch message: {response.status}")
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
    creds = service._http.credentials
    url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}/modify'
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    data = {
        "removeLabelIds": ["UNREAD"]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None
    
async def classify_order(sentence: str):
    class_names = ["summary", "read", "greating", "the other"]
    prompt = f"""\
    Classify the following sentence into one of the following categories: {",".join(class_names)}. You must return just one category and must not contain any other information. 
    Exapmle: 1. Sentences: 未読メールを要約して, ようやくして, まとめて, 要約してくれめんす。 \n Category: summary \n 2. Sentence: 既読にして, 全部読んだ, 了解, 把握した \n Category: read  \n 3. Sentence: おはよう, ばいばい, ありがとう Category: greeting
    4. うるさい, はいはい, いやいや \n Category: the other. では頑張ってください。Sentence: {sentence}"""
    print(prompt)
    response = await query_gpt3(prompt)
    return response
