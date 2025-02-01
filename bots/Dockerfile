# use an official python runtime as base
FROM python:3.12.8-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# set workdir
WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy entire codebase
COPY . .

# set telegram bot token (override at runtime or via docker-compose/env file)
ENV TELEGRAM_BOT_TOKEN=""

# start the telegram bot
CMD ["python", "bots/telegram.py", "--deep-schedule=2"]
