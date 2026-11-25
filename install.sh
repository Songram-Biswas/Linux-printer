#!/usr/bin/env bash
# ==============================================================================
# Linux Print Studio - Universal Linux Installer
# ==============================================================================
set -e

APP_NAME="linux-print-studio"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "=========================================================="
echo "         Installing Linux Print Studio                    "
echo "=========================================================="

if [ "$1" == "--uninstall" ]; then
    echo "Uninstalling $APP_NAME..."
    rm -f "$USER_BIN_DIR/$APP_NAME"
    rm -f "$DESKTOP_DIR/linux-print-studio.desktop"
    rm -f "$ICON_DIR/linux-print-studio.svg"
    echo "Uninstallation complete!"
    exit 0
fi

# 1. Detect OS & install dependencies
echo "[1/4] Checking system dependencies..."
if command -v apt-get &> /dev/null; then
    echo "Detected Debian/Ubuntu/Mint. Installing packages..."
    sudo apt-get update -qq || true
    sudo apt-get install -y python3 python3-pip python3-pyqt6 python3-pil cups-client || {
        echo "Could not install all apt packages, will check pip fallback..."
    }
elif command -v dnf &> /dev/null; then
    echo "Detected Fedora/RHEL. Installing packages..."
    sudo dnf install -y python3 python3-pip python3-pyqt6 python3-pillow cups || true
elif command -v pacman &> /dev/null; then
    echo "Detected Arch Linux/Manjaro. Installing packages..."
    sudo pacman -S --needed --noconfirm python python-pip python-pyqt6 python-pillow cups || true
fi

# 2. Check Python packages (PyMuPDF, PyQt6, Pillow)
echo "[2/4] Verifying Python libraries (PyQt6, PyMuPDF, Pillow)..."
python3 -c "import fitz" 2>/dev/null || {
    echo "Installing PyMuPDF via pip..."
    pip3 install --user PyMuPDF || pip install --user PyMuPDF || true
}

python3 -c "import PyQt6" 2>/dev/null || {
    echo "Installing PyQt6 via pip..."
    pip3 install --user PyQt6 || pip install --user PyQt6 || true
}

python3 -c "import PIL" 2>/dev/null || {
    echo "Installing Pillow via pip..."
    pip3 install --user Pillow || pip install --user Pillow || true
}

# 3. Create launcher script in ~/.local/bin
echo "[3/4] Creating launcher in $USER_BIN_DIR..."
mkdir -p "$USER_BIN_DIR"

cat << EOF > "$USER_BIN_DIR/$APP_NAME"
#!/usr/bin/env bash
exec python3 "$APP_DIR/linux_print_studio/main.py" "\$@"
EOF

chmod +x "$USER_BIN_DIR/$APP_NAME"
chmod +x "$APP_DIR/linux_print_studio/main.py"

# Ensure ~/.local/bin is in PATH in .bashrc if not already
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "Note: Adding ~/.local/bin to PATH in ~/.bashrc..."
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# 4. Install Desktop Entry & Icon
echo "[4/4] Registering Desktop Launcher & Icon..."
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"

cp "$APP_DIR/linux_print_studio/assets/icon.svg" "$ICON_DIR/linux-print-studio.svg"

sed -e "s|Exec=linux-print-studio|Exec=$USER_BIN_DIR/linux-print-studio|g" \
    "$APP_DIR/linux-print-studio.desktop" > "$DESKTOP_DIR/linux-print-studio.desktop"

chmod +x "$DESKTOP_DIR/linux-print-studio.desktop"

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "=========================================================="
echo "  Installation Successful! 🎉                             "
echo "                                                          "
echo "  You can now start Linux Print Studio by:                "
echo "  1. Running 'linux-print-studio' in any terminal.        "
echo "  2. Searching 'Linux Print Studio' in Application Menu.  "
echo "  3. Right-clicking any PDF or image -> 'Open With'.      "
echo "=========================================================="
