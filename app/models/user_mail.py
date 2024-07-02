from . import Base
from sqlalchemy import Column, Integer, String, Boolean, PrimaryKeyConstraint

# モデルの作成(User_Mail)
class User_Mail(Base):
    __tablename__ = "usermail"
    id = Column(Integer, index=True, primary_key=True)
    mail_id = Column(String, primary_key=True)
    # is_read LINEに送信したかどうか
    is_read = Column(Boolean)
    summary = Column(String)
    label_content = Column(String)
    label_name = Column(String)
    __table_args__ = (
        PrimaryKeyConstraint('id', 'mail_id'),
    )
    