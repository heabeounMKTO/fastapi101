FROM python:3.12.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

WORKDIR /home

# Dependencies first: this layer is cached until pyproject.toml / uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app app
COPY alembic alembic
COPY alembic.ini alembic.ini
COPY main.py main.py
COPY run.sh run.sh
RUN chmod +x run.sh

EXPOSE 8000
CMD ["./run.sh"]
