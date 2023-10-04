#!/bin/bash

# Dependency installation
echo "Installing dependencies..."
sudo apt-get update
if ! sudo apt-get install -y python3-pip python3-gpiozero; then
    echo "Failed to install system packages."
    exit 1
fi

# Use --user flag for pip installations
if ! pip3 install --user pydub pyaudio PyYAML; then
    echo "Failed to install Python packages."
    exit 1
fi

# Get the directory of the currently executing script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure the directory exists
if [[ ! -d "$DIR" ]]; then
    echo "Error: Directory $DIR does not exist."
    exit 1
fi

# Change ownership of the entire project directory to the current user
if ! sudo chown -R $USER:$USER "$DIR"; then
    echo "Failed to change ownership of $DIR."
    exit 1
fi

# Replace placeholders in the service file and save to temporary location
if ! sed "s|<path-to-project>|$DIR|g" "$DIR/audioGuestBook.service.template" >/tmp/audioGuestBook.service; then
    echo "sed command failed."
    exit 1
fi

# Move the modified service file to systemd directory
if ! sudo mv /tmp/audioGuestBook.service /etc/systemd/system/; then
    echo "Failed to move service file."
    exit 1
fi

# Create required directories
if ! sudo mkdir -p "$DIR/recordings"; then
    echo "Failed to create directories."
    exit 1
fi

# Set execution permissions for the main script
if ! sudo chmod +x "$DIR/audioGuestBook.py"; then
    echo "Failed to set script permissions."
    exit 1
fi

# Reload systemd, unmask, enable and start the service
sudo systemctl daemon-reload
sudo systemctl unmask audioGuestBook.service
if ! sudo systemctl enable audioGuestBook.service; then
    echo "Failed to enable the service."
    exit 1
fi
if ! sudo systemctl start audioGuestBook.service; then
    echo "Failed to start the service."
    exit 1
fi

echo "Installation completed successfully!"
