#!/bin/bash

# Set up variables
SERVICE_FILES_DIR="." # Location of your .service files
SYSTEMD_DIR="/etc/systemd/system"
DEV_MACHINE_USER="<insert your user name>"
DEV_MACHINE_IP="192.168.xx.xx"
DEV_MACHINE_ROOT="/mnt/c/Users/${DEV_MACHINE_USER}"
DEV_MACHINE_DESTINATION="${DEV_MACHINE_ROOT}/github/rotary-phone-audio-guestbook/backup"
IMG_VERSION="v1.0.3"
IMG_BACKUP_NAME="rpizero_rotary_phone_audio_guestbook_${IMG_VERSION}_imagebackup.img"
IMG_PATH="/mnt/${IMG_BACKUP_NAME}"

echo "=== Starting Deploy Script ==="

# Copy .service files to /etc/systemd/system
echo "Copying .service files to $SYSTEMD_DIR..."
sudo cp "$SERVICE_FILES_DIR"/*.service "$SYSTEMD_DIR/"

# Enable and start each service
echo "Enabling and starting services..."
for service in "$SERVICE_FILES_DIR"/*.service; do
    service_name=$(basename "$service")
    sudo systemctl enable "$service_name"
    sudo systemctl start "$service_name"
    echo "$service_name has been enabled and started."
done

# Wait for services to settle
sleep 5

# Check if a previous backup exists and perform the appropriate backup
if [ -f "$IMG_PATH" ]; then
    echo "Previous backup found. Performing incremental backup..."
    sudo image-backup "$IMG_PATH"
else
    echo "No previous backup found. Performing full backup..."
    sudo image-backup -i "$IMG_PATH"
fi

# Verify the backup's integrity with md5sum
md5sum "$IMG_PATH"

# Ensure backup image exists
if [ -f "$IMG_PATH" ]; then
    echo "Backup image created successfully."
else
    echo "Error: Backup image not created!"
    exit 1
fi

# Rsync the backup image to the local development machine
echo "Rsyncing the backup image to the local development machine..."
rsync -e ssh -avvvz "$IMG_PATH" "$DEV_MACHINE_USER@$DEV_MACHINE_IP:$DEV_MACHINE_DESTINATION/"

if [ $? -eq 0 ]; then
    echo "Rsync to local dev machine completed successfully."
else
    echo "Error during rsync. Please check the connection or destination."
    exit 1
fi

# Ask the user if they want to delete the backup image from the Raspberry Pi
read -p "Do you want to delete the backup image from the Raspberry Pi? (y/n): " delete_choice

if [[ "$delete_choice" == "y" || "$delete_choice" == "Y" ]]; then
    echo "Deleting the backup image from $IMG_PATH..."
    sudo rm -f "$IMG_PATH"
    if [ $? -eq 0 ]; then
        echo "Backup image deleted successfully."
    else
        echo "Error deleting the backup image."
    fi
else
    echo "Backup image retained at $IMG_PATH."
fi

echo "=== Deploy Script Completed Successfully ==="
