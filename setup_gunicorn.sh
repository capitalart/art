#!/bin/bash

# Script to set up Gunicorn and Flask application (ArtNarrator) without altering existing files

# Variables for paths
USER="art"
VENV_PATH="/home/$USER/venv"
APP_PATH="/home/$USER"
SERVICE_PATH="/etc/systemd/system/gunicorn.service"

# Step 1: Install system dependencies
echo "Updating system packages..."
sudo apt update
sudo apt install -y python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools

# Step 2: Create and activate the virtual environment
echo "Creating virtual environment..."
python3 -m venv $VENV_PATH

# Step 3: Activate the virtual environment and install required Python packages
echo "Activating virtual environment and installing dependencies..."
source $VENV_PATH/bin/activate

# Install Gunicorn and Flask
pip install --upgrade pip
pip install gunicorn flask

# Step 4: Create the Gunicorn systemd service file (if not already present)
if [ ! -f $SERVICE_PATH ]; then
  echo "Creating Gunicorn systemd service..."
  sudo tee $SERVICE_PATH <<EOF
[Unit]
Description=Gunicorn instance for ArtNarrator
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$APP_PATH
Environment="PATH=$VENV_PATH/bin"
Environment="FLASK_APP=app"  # Pointing to Flask app module (no .py extension)
Environment="FLASK_ENV=production"
ExecStart=$VENV_PATH/bin/gunicorn --workers 4 --bind 127.0.0.1:7777 --bind unix:/home/$USER/artnarrator.sock --access-logfile /home/$USER/logs/gunicorn-access.log --error-logfile /home/$USER/logs/gunicorn-error.log
Restart=always
RestartSec=5
LimitNOFILE=65535
LimitNPROC=65536
SyslogIdentifier=gunicorn-artnarrator

[Install]
WantedBy=multi-user.target
EOF
  echo "Gunicorn systemd service file created."
else
  echo "Gunicorn service file already exists."
fi

# Step 5: Reload systemd to apply changes
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Step 6: Enable and start the Gunicorn service
echo "Starting Gunicorn service..."
sudo systemctl enable gunicorn
sudo systemctl start gunicorn

# Step 7: Verify if Gunicorn is running correctly
echo "Verifying Gunicorn status..."
sudo systemctl status gunicorn

# Final message
echo "Setup complete! Your Gunicorn service is running and will start on boot."
