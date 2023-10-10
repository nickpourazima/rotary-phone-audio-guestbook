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

# Prompt user for config values
echo "Please provide your configuration values:"

while true; do
    read -p "alsa_hw_mapping (default 1): " alsa_hw_mapping
    alsa_hw_mapping=${alsa_hw_mapping:-1}
    if [[ "$alsa_hw_mapping" =~ ^[0-9]+$ ]]; then
        break
    else
        echo "Invalid number. Please enter a non-negative integer for alsa_hw_mapping."
    fi
done

while true; do
    read -p "number of microphone channels (default 2): " channels
    channels=${channels:-2}
    if [[ "$channels" =~ ^[1-9][0-9]*$ ]]; then
        break
    else
        echo "Invalid number. Please enter a positive integer for channels."
    fi
done

while true; do
    read -p "recording sample rate (default 44100): " sample_rate
    sample_rate=${sample_rate:-44100}
    if [[ "$sample_rate" =~ ^[89][0-9]{3}$|^[1-9][0-9]{4}$|^[1][0-8][0-9]{4}$|192000$ ]]; then
        break
    else
        echo "Invalid sample rate. Please enter a value between 8000 and 192000."
    fi
done

while true; do
    read -p "recording format - INT16, INT32, FLOAT32 (default INT16): " format
    format=${format:-INT16}
    if [[ "$format" =~ ^(INT16|INT32|FLOAT32)$ ]]; then
        break
    else
        echo "Invalid format. Please choose from INT16, INT32, or FLOAT32."
    fi
done

while true; do
    read -p "hook type - normally open (NO) or normally closed (default NC): " hook_type
    hook_type=${hook_type:-NC}
    if [[ "$hook_type" =~ ^(NO|NC)$ ]]; then
        break
    else
        echo "Invalid hook type. Please enter either NO or NC."
    fi
done

while true; do
    read -p "hook_gpio (default 22): " hook_gpio
    hook_gpio=${hook_gpio:-22}
    if [[ "$hook_gpio" =~ ^[0-9]+$ ]]; then
        break
    else
        echo "Invalid GPIO pin number. Please enter a non-negative integer."
    fi
done

while true; do
    read -p "recording_limit - in seconds (default 300): " recording_limit
    recording_limit=${recording_limit:-300}
    if [[ "$recording_limit" =~ ^[0-9]+$ ]]; then
        break
    else
        echo "Invalid recording limit. Please enter a non-negative integer for the number of seconds."
    fi
done

# Confirm before overwriting
read -p "This will overwrite the current config.yaml. Are you sure? (Y/N): " overwrite
if [[ "$overwrite" != "Y" ]]; then
    echo "Config update aborted."
    exit 1
fi

cat <<EOF >"$DIR/config.yaml"
alsa_hw_mapping: $alsa_hw_mapping
beep_reduction: 24
buffer_size: 4096
channels: $channels
hook_gpio: $hook_gpio
playback_reduction: 16
recording_limit: $recording_limit
rotary_gpio: 23
rotary_hold_repeat: true
rotary_hold_time: 0.25
sample_rate: $sample_rate
source_file: audioGuestBook.py
format: $format
hook_type: $hook_type
EOF

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
