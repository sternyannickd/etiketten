#!/bin/sh
# Legt einen Eintrag "Etikettendruck" im Startmenü an (Linux Mint / Cinnamon u. a.).
set -e
PROJEKT="$(cd "$(dirname "$0")/.." && pwd)"
ZIEL="$HOME/.local/share/applications/etikettendruck.desktop"
mkdir -p "$(dirname "$ZIEL")"
cat > "$ZIEL" <<EOD
[Desktop Entry]
Type=Application
Name=Etikettendruck
Comment=Etiketten auf dem Citizen drucken
Exec=$PROJEKT/start.sh
Icon=printer
Terminal=true
Categories=Office;
EOD
echo "Startmenü-Eintrag angelegt: $ZIEL"
