#!/bin/bash
echo "╔══╣ Install: speech_recognition_nemo (STARTING) ╠══╗"

# Keep the current directory for later use
SCRIPT_DIR=$(pwd)

# Exit immediately if a command exits with a non-zero status.
set -e

# --- System Package Installation ---
echo "--- Updating apt package lists and installing system dependencies ---"
export DEBIAN_FRONTEND=noninteractive # Skip interactive apt prompts

sudo apt update -y

# Install apt packages one by one, automatically answering 'yes' to prompts
yes | sudo apt install -y ros-humble-vision-msgs
echo "System dependencies installed."

echo "Install pulsectl"
pip3 install pulsectl -y

SOBITS_MSGS_REPO="sobits_interfaces"
# Check if the repository already exists
if [ ! -d "$SOBITS_MSGS_REPO" ]; then
    echo "Cloning $SOBITS_MSGS_REPO repository..."
    git clone -b humble-devel https://github.com/TeamSOBITS/sobits_interfaces.git
    echo "$SOBITS_MSGS_REPO cloned successfully."
else
    echo "$SOBITS_MSGS_REPO repository already exists. Skipping clone."
fi


echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", ATTRS{serial}=="74:4D:BD:7F:1B:28", MODE="0666", SYMLINK+="esp32_board_a"' | sudo tee /etc/udev/rules.d/99-esp32.rules

echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", ATTRS{serial}=="30:ED:A0:A8:A4:DC", MODE="0666", SYMLINK+="esp32_board_b"' | sudo tee -a /etc/udev/rules.d/99-esp32.rules 

sudo udevadm control --reload-rules

sudo udevadm trigger

echo "╚══╣ Install: speech_recognition_nemo (FINISHED) ╠══╝"