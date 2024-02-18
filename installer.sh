#!/bin/bash

# Rotary Phone Audio Guestbook Installer

echo "Starting the installation process..."

# Update and install system dependencies
echo "Installing additional dependencies..."
sudo apt-get install -y python3-pip python3-venv python3-gpiozero ffmpeg || {
    echo "Failed to install required system packages."
    exit 1
}

# Set up Python virtual environment for project dependencies
echo "Setting up Python virtual environment..."
python3 -m venv ~/rotary-phone-venv || {
    echo "Failed to create Python virtual environment."
    exit 1
}
source ~/rotary-phone-venv/bin/activate

# Install Python dependencies in the virtual environment
pip install pydub pyaudio PyYAML sounddevice || {
    echo "Failed to install Python dependencies."
    exit 1
}

# Modify PulseAudio configuration for improved audio handling
echo "Configuring PulseAudio..."
sudo cp /etc/pulse/default.pa /etc/pulse/default.pa.backup
echo -e "default-fragments = 5\ndefault-fragment-size-msec = 2" | sudo tee -a /etc/pulse/default.pa

# Restart PulseAudio to apply changes
pulseaudio -k
pulseaudio --start

# Display available sound cards and devices
echo "Listing available sound cards and devices:"
aplay -l

# Prompt user for ALSA configuration values
echo "Configuring ALSA..."
read -p "Enter the card number for the default playback card (e.g., 0, 1): " playback_card
read -p "Enter the card number for the default capture card (e.g., 0, 1): " capture_card
read -p "Enter the default sample rate (e.g., 44100): " sample_rate
while ! [[ "$sample_rate" =~ ^[89][0-9]{3}$|^[1-9][0-9]{4}$|^[1][0-8][0-9]{4}$|192000$ ]]; do
    echo "Invalid sample rate. Please enter a value between 8000 and 192000."
    read -p "Enter the default sample rate (e.g., 44100): " sample_rate
done

read -p "Enter the bit depth (16, 24, 32): " bit_depth
while ! [[ "$bit_depth" =~ ^(16|24|32)$ ]]; do
    echo "Invalid bit depth. Please choose from 16, 24, or 32."
    read -p "Enter the bit depth (16, 24, 32): " bit_depth
done

# Write ALSA configuration
echo "Applying ALSA configuration..."
sudo tee /etc/asound.conf >/dev/null <<EOF
# Custom ALSA configuration for Rotary Phone Audio Guestbook
defaults.pcm.rate_converter "samplerate"
defaults.pcm.dmix.rate $sample_rate
defaults.pcm.dmix.format S$bit_depth
defaults.ctl.card $playback_card
defaults.pcm.card $playback_card
defaults.pcm.device 0
defaults.pcm.subdevice -1
defaults.pcm.nonblock 1
defaults.pcm.compat 0
pcm.!default {
    type hw
    card $playback_card
}
ctl.!default {
    type hw
    card $capture_card
}
EOF

# Test recording and playback functionality
echo "Testing recording and playback..."
arecord -D hw:$capture_card,0 -d 5 -f cd test-mic.wav && aplay test-mic.wav || {
    echo "Test failed. Check your microphone and speaker setup."
    exit 1
}

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
if ! sudo chmod +x "$DIR/src/audioGuestBook.py"; then
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
