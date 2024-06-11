from . import Base
from sqlalchemy import Column, Integer, String, Boolean

# モデルの作成(User_Mail)
class User_Mail(Base):
    __tablename__ = "usermail"
    id = Column(String, primary_key=True, index=True)
    mail_id = Column(Integer)
    is_read = Column(Boolean)
    