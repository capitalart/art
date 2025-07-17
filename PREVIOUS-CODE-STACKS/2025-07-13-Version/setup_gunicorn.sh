#!/bin/bash

# ===== ART Narrator Flask Gunicorn Service Setup Script =====
# For user: artlistmachine
# Project dir: /home/artlistmachine/capitalart
# Venv: /home/artlistmachine/capitalart/venv
# Flask app: app.py (entrypoint app:app)
# Port: 8000

USER="artlistmachine"
GROUP="artlistmachine"
PROJECT_DIR="/home/artlistmachine/capitalart"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="capitalart"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# 1. Install Gunicorn if not present in venv
echo ">>> [1/5] Ensuring Gunicorn is installed in your virtualenv..."
source "$VENV_DIR/bin/activate"
pip show gunicorn > /dev/null 2>&1
if [ $? -ne 0 ]; then
  pip install gunicorn
else
  echo "Gunicorn already installed."
fi
deactivate

# 2. Create the systemd service file
echo ">>> [2/5] Writing the systemd service file..."
cat << EOF > ${SERVICE_NAME}.service
[Unit]
Description=ART Narrator Flask Gunicorn Service
After=network.target

[Service]
User=${USER}
Group=${GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 3. Move the service file to /etc/systemd/system/ (requires sudo)
echo ">>> [3/5] Installing the service file (you may need to enter your password)..."
sudo mv ${SERVICE_NAME}.service $SERVICE_FILE
sudo chmod 644 $SERVICE_FILE

# 4. Reload systemd, enable and start the service
echo ">>> [4/5] Reloading systemd, enabling and starting your service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

# 5. Show useful info
echo ">>> [5/5] All done!"
echo ""
echo "To check service status:     sudo systemctl status $SERVICE_NAME"
echo "To view live logs:           journalctl -u $SERVICE_NAME -f"
echo "To restart after code edits: sudo systemctl restart $SERVICE_NAME"
echo ""
echo "Your site should now run 24/7, even after closing VSCode or rebooting."
