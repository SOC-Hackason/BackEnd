import google.auth
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
SERVICE_ACCOUNT_FILE = 'path/to/your-service-account-file.json'
PROJECT_ID = 'YOUR_PROJECT_ID'
TOPIC_NAME = 'projects/YOUR_PROJECT_ID/topics/gmail-notifications'

credentials = google.auth.load_credentials_from_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('gmail', 'v1', credentials=credentials)

user_id = 'me'
request = {
    'labelIds': ['INBOX'],
    'topicName': TOPIC_NAME
}

response = service.users().watch(userId=user_id, body=request).execute()
print('Push Notification Watch Response:', response)
