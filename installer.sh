#!/bin/bash

# Dependency installation
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-gpiozero
pip3 install pydub pyaudio PyYAML

# Get the directory of the currently executing script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Replace placeholders in the service file and save to temporary location
sed "s|<path-to-project>|$DIR|g" rotaryGuestBook.service.template > /tmp/rotaryGuestBook.service

# Move the modified service file to systemd directory
sudo mv /tmp/rotaryGuestBook.service /etc/systemd/system/

# Create required directories
mkdir -p $DIR/recordings

# Set permissions for python scripts
chmod +x $DIR/audioGuestBook.py
chmod +x $DIR/audioInterface.py

# Reload systemd, enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable rotaryGuestBook.service
sudo systemctl start rotaryGuestBook.service
