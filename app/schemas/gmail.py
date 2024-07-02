from pydantic import BaseModel

class OAuth2Code(BaseModel):
    code: str

class FreeMessage(BaseModel):
    sentence: str
    line_id: str