# util file for gmail api

def create_label(service, label_name):
    """Create a label in gmail account if it does not already exist\n
    Args:\n
    service: Gmail service object\n
    label_name: Name of the label to be created\n
    Returns:\n
    label: The created label object\n
    """
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
    

def get_unread_message(service):
    """Get all unread messages in the inbox\n
    Args:\n
    service: Gmail service object\n
    Returns:\n
    messages: List of unread messages\n
    """
    try:
        messages = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD']
        ).execute()
        return messages
    except Exception as e:
        return None

def get_message_from_id(service, msg_ids:list):
    """Get a message from its id\n
    Args:\n
    service: Gmail service object\n
    msg_id: The ids of the message to be fetched\n
    Returns:\n
    message: The fetched messages\n
    """
    try:
        messages = []
        for msg_id in msg_ids:
            message = service.users().messages().get(
                userId='me',
                id=msg_id
            ).execute()
            messages.append(message)
        return messages
    except Exception as e:
        return None