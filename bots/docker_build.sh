#!/bin/bash

set -e

docker build \
       --file bots/Dockerfile \
       -t libreagent-telegram \
       .
