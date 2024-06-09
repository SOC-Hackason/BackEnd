from . import Base
from sqlalchemy import Column, Integer, String

# モデルの作成(Sample)
class Sample(Base):
    __tablename__ = "sample"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer)
    address = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    phone_number = Column(String)