#!/bin/bash
echo "╔══╣ Install: esp32 display (STARTING) ╠══╗"

# Keep the current directory for later use
SCRIPT_DIR=$(pwd)

# Exit immediately if a command exits with a non-zero status.
set -e

# --- System Package Installation ---
echo "--- Updating apt package lists and installing system dependencies ---"
export DEBIAN_FRONTEND=noninteractive # Skip interactive apt prompts

sudo apt update -y

# Install apt packages one by one, automatically answering 'yes' to prompts
yes | sudo apt install -y ros-${ROS_DISTRO}-vision-msgs
echo "System dependencies installed."

# --- Python Package Installation ---
echo "--- Installing Python dependencies ---"
pip3 install pulsectl pyserial --break-system-package

cd ..

SOBITS_MSGS_REPO="sobits_interfaces"
# Check if the repository already exists
if [ ! -d "$SOBITS_MSGS_REPO" ]; then
    echo "Cloning $SOBITS_MSGS_REPO repository..."
    git clone -b feature/display_control https://github.com/TeamSOBITS/sobits_interfaces.git
    echo "$SOBITS_MSGS_REPO cloned successfully."
else
    echo "$SOBITS_MSGS_REPO repository already exists. Skipping clone."
fi

echo "╚══╣ Install: esp32 display (FINISHED) ╠══╝"