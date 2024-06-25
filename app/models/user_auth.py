from . import Base
from sqlalchemy import Column, Integer, String, Time


class User_Auth(Base):
    __tablename__ = "userauth"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String)
    notify_time = Column(Time)
    refresh_token = Column(String)
    access_token = Column(String)
