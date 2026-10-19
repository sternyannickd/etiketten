#!/bin/sh
# Baut installer/Etikettendruck-Installer-Linux.sh aus dist/etikettendruck/.
# Vorher: pyinstaller --noconfirm packaging/etikettendruck.spec
set -eu
PROJEKT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJEKT"
VERSION=$(python3 -c "import etiketten; print(etiketten.__version__)")
[ -x dist/etikettendruck/etikettendruck ] || { echo "Erst PyInstaller ausführen (dist/etikettendruck fehlt)" >&2; exit 1; }
cp packaging/symbol.png dist/etikettendruck/_internal/symbol.png
mkdir -p installer
ZIEL=installer/Etikettendruck-Installer-Linux.sh
# Das Archiv als Text (base64): So erkennt der Dateimanager den Installer sicher als Skript.
sed "s/@VERSION@/$VERSION/" packaging/linux/installer-kopf.sh > "$ZIEL.tmp"
tar -czf - -C dist etikettendruck | base64 -w 76 >> "$ZIEL.tmp"
chmod 755 "$ZIEL.tmp"
mv "$ZIEL.tmp" "$ZIEL"
echo "Gebaut: $ZIEL ($(du -h "$ZIEL" | cut -f1))"
