#!/bin/bash
set -e

echo "Detecting OS..."

OS_TYPE="$(uname | tr '[:upper:]' '[:lower:]')"
echo "OS detected: $OS_TYPE"

if [[ "$OS_TYPE" == "linux" ]]; then
    echo "Updating package list and installing Inkscape on Linux..."
    if command -v sudo >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y inkscape
    else
        echo "Warning: sudo not found, trying apt-get directly..."
        apt-get update
        apt-get install -y inkscape
    fi
    echo "Inkscape version:"
    inkscape --version

elif [[ "$OS_TYPE" == "mingw"* ]] || [[ "$OS_TYPE" == "msys"* ]] || [[ "$OS_TYPE" == "cygwin"* ]]; then
    echo "Windows environment detected (MSYS2/Git Bash)..."
    if ! command -v pacman >/dev/null 2>&1; then
        echo "MSYS2 pacman not found. Install MSYS2 first: https://www.msys2.org/"
        exit 1
    fi
    echo "Updating MSYS2 packages..."
    pacman -Syu --noconfirm
    echo "Installing Inkscape..."
    pacman -S --noconfirm inkscape
    echo "Inkscape version:"
    inkscape --version

else
    echo "Unsupported OS. Please install Inkscape manually."
    exit 1
fi

echo "Inkscape installation completed!"
