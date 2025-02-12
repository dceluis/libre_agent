# use an official python runtime as base
FROM python:3.12.8-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# set workdir
WORKDIR /app

# install dependencies
RUN pip install uv

COPY pyproject.toml ./
COPY uv.lock ./

RUN uv sync

# copy entire codebase
COPY ./libre_agent ./libre_agent
COPY ./bots ./bots

# set telegram bot token (override at runtime or via docker-compose/env file)
ENV TELEGRAM_BOT_TOKEN=""

# start the telegram bot
CMD ["uv", "run", "bots/telegram.py", "--deep-schedule=2", "--memory-graph-file=tmp.pkl"]
