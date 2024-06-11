from sqlalchemy import Column, Integer, String, MetaData
from sqlalchemy.orm import sessionmaker
from databases import Database
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
Base = declarative_base()

# 環境変数からデータベースのURLを取得
import os
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:mailsommelier@db:5432/mydatabase")
IS_CLEAR = os.getenv("IS_CLEAR", True)
if IS_CLEAR == "True" or IS_CLEAR:
    IS_CLEAR = True
else:
    IS_CLEAR = False

print(DATABASE_URL, IS_CLEAR)

# SQLAlchemyの設定
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
# ベースモデルの作成
# databasesライブラリのデータベースオブジェクト
database = Database(DATABASE_URL)

# データベースとのセッションを提供する依存関係

async def get_db():
    async with SessionLocal() as session:
        yield session



