# Pythonの公式イメージをベースに使用
FROM python:3.10-slim

# 作業ディレクトリの設定
WORKDIR /temp

# 必要な依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコンテナ内にコピー
COPY ./app ./app

# uvicornでアプリケーションをホストするためのコマンドを設定
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
