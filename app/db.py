from sqlalchemy import Column, Integer, String, MetaData
from sqlalchemy.orm import sessionmaker
from databases import Database
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
Base = declarative_base()

# 環境変数からデータベースのURLを取得
import os
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:mailsommelier@db:5432/mydatabase")
IS_CLEARDB = os.getenv("IS_CLEARDB", "True")
if IS_CLEARDB == "True":
    IS_CLEARDB = True
else:
    IS_CLEARDB = False

print(DATABASE_URL, IS_CLEARDB)

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

async def get_db_session():
    return SessionLocal()


