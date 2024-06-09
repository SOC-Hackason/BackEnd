# BackEnd
## 起動の仕方(docker)
```
docker-compose up
```
これでlocalhost:8000/docsにアクセスしてもらうのが、基本的な使い方になると思います。windowsの人は[docker-desktop](https://www.docker.com/get-started/)でインストールしてください。

## 起動の仕方(local)
適当なデータベースを用意して(MySQL, PostGreSQL, SQLite3)
db.pyのSQLURLを書き換えて必ず作業ディレクトリはappの上でやってください。C:\xxx\xxx\BackEnd\\>とかになると思います。
```
uvicorn app.main:app --host 0.0.0.0 --port 80 --reload
```
## デプロイ
未定

## 開発
[ディレクトリ構成書くときに便利なやつ](https://tree.nathanfriend.io/)
```
/temp #dockerの場合
│
├── app/              # アプリケーションのソースファイル
│   ├── __init__.py   
│   ├── main.py       # FastAPI アプリケーションのエントリポイント
│   ├── db.py         # データベースの接続とか
│   │
│   ├── models/       # データベースモデル
│   │   ├── __init__.py
│   │   └── sample.py # sampleモデル
│   └── schemas/      # Pydantic モデル（リクエストとレスポンスのスキーマ）
│       ├── __init__.py
│       └── sample.py #またやる
├── requirements.txt  # 必要なパッケージとライブラリ
└── Dockerfile        # Docker イメージの構築のための設定
```

## 開発の仕方
```
# 仮想環境の構築（スキップ可）
python -m venv backend
# ライブラリのインストール <-　ハイライト用
pip install -r requirements.txt
# 起動
docker-compose up
```
なんかよくわからなくなったら、dockerコンテナの中に入るのも手です。vscodeのremote Explorer(Docker)や
```
# Container ID確認
docker ps
docker exec -it xxxx /bin/bash
or
docker exec -it xxxx sh
```
などでコンテナ内部に入れます。


## 開発の方向性
gmailAPIを叩くメソッドはapp/routers/gmail.pyに書きたい
LINEAPI...

ユーザーごとにrefreshTokenをdbに保存する必要がある。

## FastAPIの基本
[FastAPIチュートリアル](https://fastapi.tiangolo.com/ja/tutorial/)
```python
#rootアクセスポイントにgetしたとき
@app.get("/")
async def read_root():
    #なんでもjsonにして返すはず
    return {"Hello": "World"}

#パラメータはパスパラメータ(item_id)、クエリパラメータ(q)、リクエストボディの三種類？
#例えば今回だとlocalhost:8000/items/100?q=fastapiでGETすると
#item_id=100, q=fastapiになる
@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
```
