FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 仮想環境は /venv に作成し、ソースコードのマウントで隠れないようにする。
ENV UV_PROJECT_ENVIRONMENT=/venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 音声ファイルの読み込みに必要なライブラリをインストールする。
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# EmbeddingGemma 2 の画像・音声対応プロセッサを利用する。
RUN uv init --bare && \
    uv add fastapi uvicorn torch torchvision "transformers>=5.18.0" "sentence-transformers>=6.1.0" pillow librosa soundfile audioread python-multipart

COPY . .

ENV PATH="/venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]