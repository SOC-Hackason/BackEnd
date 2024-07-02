from . import Base
from sqlalchemy import Column, Integer, String


class User_Line(Base):
    __tablename__ = "userline"
    id = Column(Integer, primary_key=True, autoincrement=True)
    line_id = Column(String, index=True, unique=True)
