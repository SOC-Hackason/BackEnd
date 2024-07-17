import requests
from app.settings import GPT_TOKEN
import aiohttp

async def query_gpt3(prompt, api_key=GPT_TOKEN):
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a nice secretary. You are in charge of everything related to emails."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "n": 1,
        "stop": None,
        "temperature": 0.7
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                response_data = await response.json()
                return response_data['choices'][0]['message']['content']
            else:
                return f"Error: {response.status}, {await response.text()}"
        
    
async def summarise_email(email_content, api_key=GPT_TOKEN, language="Japanese"):
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_message = "You are a secretary. You are good at summarizing email. You can summarize your email in no more than three sentences."
    prompt = f"Summarize the following email in {language}. You have to sammarize in {language} shortly and very briefly like 1 or 2 sentences. In addition, you have to remove url because it may be spam.:\n\n{email_content}"

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "n": 1,
        "stop": None,
        "temperature": 0.7
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                response_data = await response.json()
                return response_data['choices'][0]['message']['content']
            else:
                return f"Error: {response.status}, {await response.text()}"

def categorize_email(email_content, api_key = GPT_TOKEN):
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_message = "You are a secretary.You are good at email classification."
    categories = ["Work", "School", "Social", "Spam", "Other"]
    categories_text = ", ".join(categories)

    prompt = f"""
    Categorize the following email into one of the following categories: {categories_text}.
    Format the output as:
    カテゴリー: [Category]'
    
    Email content:
    {email_content}
    """

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "n": 1,
        "stop": None,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
    else:
        return f"Error: {response.status_code}, {response.text}"
def join_Emails(mails):
    result = "\n" + ("\n" + "=="+ "\n").join(mails) + "\n"
    return result

def summarise_emails(mails, api_key=GPT_TOKEN):

    email_contents = join_Emails(mails=mails)
    mail_num = len(mails)

    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_message = "You are a secretary.You are good at summarizing email. You can summarise your email in no more than three sentences."
    prompt =  f"Summarize the following {mail_num} emails in Japanese as shortly as possible:\n\n{email_contents}"

   
    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "n": 1,
        "stop": None,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
    else:
        return f"Error: {response.status_code}, {response.text}"
