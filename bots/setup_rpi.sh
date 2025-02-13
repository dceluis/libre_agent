#!/bin/bash

# --- Function Definitions ---

# Function to check if a command exists
command_exists() {
  command -v "$1" &> /dev/null
}

# Function to install Docker using the convenience script
install_docker() {
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  rm get-docker.sh
  sudo usermod -aG docker $USER
  echo "Docker installed.  You may need to log out and back in for group changes to take effect."
  echo "Please run 'newgrp docker' or log out and back in before continuing."
  exit 0  # Exit to allow the user to log out/in or run newgrp
}

# Function to install bpytop
install_bpytop() {
  echo "Installing bpytop..."
  sudo apt-get update
  sudo apt-get install -y bpytop
}

# Function to load environment variables from .env
load_env() {
    if [ -f .env ]; then
        echo "Loading environment variables from .env"
        # shellcheck disable=SC1090
        export $(grep -v '^#' .env | xargs)
    else
        echo "Warning: .env file not found.  Using default environment variables."
    fi
}

# --- Main Script ---

set -e  # Exit on any error

# Check for Docker
if ! command_exists docker; then
  install_docker
fi

# Check for Docker Compose (as a plugin - the modern way)
#  We verify that 'docker compose version' works.
if ! docker compose version &> /dev/null; then
  echo "Installing Docker Compose plugin..."
  sudo apt-get update
  sudo apt-get install -y docker-compose-plugin
fi

# Check for bpytop
if ! command_exists bpytop; then
  install_bpytop
fi

# Check for tmux
if ! command_exists tmux; then
  echo "Installing tmux..."
  sudo apt-get update
  sudo apt-get install -y tmux
fi

# Load environment variables
load_env

# Start tmux session
if ! tmux has-session -t libreagent 2> /dev/null; then
  echo "Creating new tmux session: libreagent"

  # Run docker-compose in the first pane
  tmux new-session -d -s libreagent -n docker-compose  "docker compose up --build"

  # Run bpytop in the second pane
  tmux split-window -h -t libreagent:0.0
  tmux send-keys -t libreagent:0.1 "bpytop" Enter

  # Attach to the session
  tmux attach-session -t libreagent
else
  echo "tmux session 'libreagent' already exists.  Attaching..."
  tmux attach-session -t libreagent
fi
