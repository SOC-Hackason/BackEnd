from . import Base
from sqlalchemy import Integer, Column, LargeBinary


class User_Weight(Base):
    __tablename__ = "userweight"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_weight = Column(LargeBinary)