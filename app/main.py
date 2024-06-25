from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware


from app.routers import gmail # ルーターモジュールをインポート
from app.db import database, engine, IS_CLEARDB
from app.models import Base



# FastAPIインスタンスが作成されたときにdbと繋いで、インスタンスが終了したときにdbを閉じる
@asynccontextmanager
async def lifespan(app: FastAPI):
    # データベース接続の開始
    if IS_CLEARDB:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            print("データベースを初期化しました")
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await database.connect()
    yield
    # データベース接続の終了
    await database.disconnect()

app = FastAPI(lifespan=lifespan)
# CORSミドルウェアの追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key="secret")

import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# ルーターをアプリケーションに追加
app.include_router(gmail, prefix="/gmail", tags=["gmail"])

@app.get("/")
async def read_root():
    return {"Hello": "World"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
