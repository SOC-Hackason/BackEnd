import requests
from app.settings import GPT_TOKEN

def summarise_email(email_content, api_key=GPT_TOKEN):
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_message = "You are a secretary.You are good at summarizing email.You can summarise your email in no more than three sentences."
    prompt = f"Summarize the following email in Japanese:\n\n{email_content}"

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

def categorize_email(email_content, api_key = GPT_TOKEN):
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    system_message = "You are a secretary.You are good at email classification."
    categories = ["Work", "School", "Social", "Spam", "Other"]
    categories_text = ", ".join(categories)

    prompt = f"Summarize the following email in Japanese:\n\n{email_content}"
    prompt = f"""
    Categorize the following email into one of the following categories: {categories_text}.
    Format the output as:
    カテゴリー: [Category]'
    
    Email content:
    {email_content}
    """

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

