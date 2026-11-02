FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 仮想環境は /venv に作成し、アプリのソースコードと分けて管理する。
ENV UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

ENV PATH="/venv/bin:$PATH"

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]