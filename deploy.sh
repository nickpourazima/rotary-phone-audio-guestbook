#!/bin/bash

# Set up variables

# Raspberry Pi (target device)
RPI_USER="admin"
RPI_IP="192.168.xx.xx"
RPI_PROJECT_DIR="/home/${RPI_USER}/rotary-phone-audio-guestbook"
RPI_SYSTEMD_DIR="/etc/systemd/system"

# Image backup settings
IMG_VERSION="v1.0.4"
IMG_BACKUP_NAME="rpizero_rotary_phone_audio_guestbook_${IMG_VERSION}_imagebackup.img"
IMG_PATH="/mnt/${IMG_BACKUP_NAME}"

# Local backup directory
BACKUP_DIR="./backup"

echo "=== Starting Deploy Script ==="

# Step 1: Sync files from local machine to Raspberry Pi
echo "Syncing files from local machine to Raspberry Pi..."
rsync -avz --exclude-from='./rsync-exclude.txt' ./ ${RPI_USER}@${RPI_IP}:${RPI_PROJECT_DIR}/

# Step 2: SSH into the Raspberry Pi to execute commands there
echo "Connecting to Raspberry Pi to complete deployment..."
ssh ${RPI_USER}@${RPI_IP} <<ENDSSH
    # Copy service files to systemd directory
    echo "Copying service files to systemd directory..."
    sudo cp ${RPI_PROJECT_DIR}/*.service ${RPI_SYSTEMD_DIR}/

    # Enable and restart services
    echo "Enabling and restarting services..."
    sudo systemctl daemon-reload
    sudo systemctl enable audioGuestBook.service
    sudo systemctl restart audioGuestBook.service
    sudo systemctl enable audioGuestBookWebServer.service
    sudo systemctl restart audioGuestBookWebServer.service

    # Wait for services to settle
    sleep 5

    # Create image backup
    echo "Creating image backup..."

    # Check if current version backup exists
    if [ -f "${IMG_PATH}" ]; then
        echo "Current version backup found. Performing incremental backup..."
        sudo image-backup "${IMG_PATH}"
    else
        # Try to find previous versions (v1.0.3, v1.0.2, etc.)
        PREV_FOUND=false

        # Try v1.0.3
        PREV_PATH="/mnt/rpizero_rotary_phone_audio_guestbook_v1.0.3_imagebackup.img"
        if [ -f "\${PREV_PATH}" ]; then
            echo "Found previous version v1.0.3. Using for incremental backup..."
            sudo image-backup "\${PREV_PATH}" "${IMG_PATH}"
            PREV_FOUND=true
        fi

        # If previous not found, check v1.0.2
        if [ "\${PREV_FOUND}" = "false" ]; then
            PREV_PATH="/mnt/rpizero_rotary_phone_audio_guestbook_v1.0.2_imagebackup.img"
            if [ -f "\${PREV_PATH}" ]; then
                echo "Found previous version v1.0.2. Using for incremental backup..."
                sudo image-backup "\${PREV_PATH}" "${IMG_PATH}"
                PREV_FOUND=true
            fi
        fi

        # If still no previous version, do full backup
        if [ "\${PREV_FOUND}" = "false" ]; then
            echo "No previous versions found. Performing full backup..."
            sudo image-backup -i "${IMG_PATH}"
        fi
    fi

    # Verify the backup was created
    if [ -f "${IMG_PATH}" ]; then
        echo "Backup image created successfully."
        echo "Calculating MD5 checksum..."
        md5sum "${IMG_PATH}"
    else
        echo "Error: Backup image not created!"
        exit 1
    fi
ENDSSH

# Check if SSH command was successful
if [ $? -ne 0 ]; then
    echo "Error: SSH connection or remote commands failed."
    exit 1
fi

# Step 3: Copy the backup image from Raspberry Pi to development machine
echo "Copying backup image from Raspberry Pi to local machine..."
mkdir -p "${BACKUP_DIR}"
rsync -avz ${RPI_USER}@${RPI_IP}:${IMG_PATH} "${BACKUP_DIR}/"

if [ $? -eq 0 ]; then
    echo "Backup image copied to local machine successfully."
else
    echo "Error during backup image transfer. Please check the connection or destination."
    exit 1
fi

# Step 4: Ask if you want to delete the backup from the Raspberry Pi
read -p "Do you want to delete the backup image from the Raspberry Pi? (y/n): " delete_choice

if [[ "$delete_choice" == "y" || "$delete_choice" == "Y" ]]; then
    echo "Deleting backup image from Raspberry Pi..."
    ssh ${RPI_USER}@${RPI_IP} "sudo rm -f ${IMG_PATH}"

    if [ $? -eq 0 ]; then
        echo "Backup image deleted from Raspberry Pi successfully."
    else
        echo "Error deleting the backup image from Raspberry Pi."
    fi
else
    echo "Backup image retained on Raspberry Pi at ${IMG_PATH}."
fi

echo "=== Deploy Script Completed Successfully ==="
