from pydantic import BaseModel
from typing import List, Dict

class OAuth2Code(BaseModel):
    code: str

class FreeMessage(BaseModel):
    sentence: str
    line_id: str

class MailMessages(BaseModel):
    message: List[str]
    msg_ids: List[Dict[str, str]]