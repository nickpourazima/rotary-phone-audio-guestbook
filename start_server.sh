#!/bin/bash
source /home/admin/rotary-phone-audio-guestbook/.venv/bin/activate
IP_ADDRESS=$(/sbin/ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
exec gunicorn -w 1 -k gevent -b ${IP_ADDRESS}:8000 webserver.server:app