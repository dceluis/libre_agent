#!/bin/bash

docker run \
       -it --rm \
       -v `pwd`:/app \
       -e GEMINI_API_KEY=$GEMINI_API_KEY \
       -e TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN \
       -e HISTFILE=/app/.bash_history \
       -e PROMPT_COMMAND='history -a' \
       -e HISTCONTROL=ignoredups \
       -e HISTSIZE=10000 \
       -e HISTFILESIZE=20000 \
       libreagent-telegram \
       bash
