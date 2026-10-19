#!/bin/sh
# Etikettendruck – Installer für Linux
#
# Doppelklicken und „Ausführen“ wählen (oder im Terminal: sh <diese Datei>).
# Installiert nur für den angemeldeten Benutzer, ohne Adminrechte:
#   Programm:     ~/.local/opt/etikettendruck/        (wird bei jedem Update ersetzt)
#   Eigene Daten: ~/.local/share/etikettendruck/      (bleiben bei Updates erhalten)
# Erneut ausführen = Update. Deinstallieren: ~/.local/opt/etikettendruck/deinstallieren.sh
set -eu

VERSION="@VERSION@"
ZIEL="$HOME/.local/opt/etikettendruck"
ANWENDUNGEN="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SYMBOLE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

grafisch() { [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; }
info()   { echo "$1"; if grafisch; then zenity --info --title="Etikettendruck" --width=420 --text="$1" 2>/dev/null || true; fi; }
fehler() { echo "FEHLER: $1" >&2; if grafisch; then zenity --error --title="Etikettendruck" --width=420 --text="$1" 2>/dev/null || true; fi; exit 1; }
frage()  { if grafisch; then zenity --question --title="Etikettendruck" --width=420 --text="$1" 2>/dev/null; else
             printf '%s [j/N] ' "$1"; read -r a; [ "$a" = j ] || [ "$a" = J ]; fi; }

[ "$(id -u)" -ne 0 ] || fehler "Bitte nicht als root bzw. mit sudo ausführen, sondern als normaler Benutzer."
case "$(uname -m)" in x86_64|amd64) ;; *) fehler "Dieser Installer ist für 64-Bit-PCs (x86_64), nicht für $(uname -m)." ;; esac
for befehl in tar base64 awk; do
    command -v "$befehl" >/dev/null 2>&1 || fehler "Benötigtes Programm fehlt: $befehl"
done

# 1. Laufendes Programm beenden (bei einem Update)
pkill -f "$ZIEL/etikettendruck" 2>/dev/null || true

# 2. Programm auspacken – erst in einen Nachbarordner, dann in einem Schritt austauschen
mkdir -p "$(dirname "$ZIEL")"
NEU="$ZIEL.neu.$$"
rm -rf "$NEU"; mkdir -p "$NEU"
trap 'rm -rf "$NEU"' EXIT
ZEILE=$(awk '/^__ARCHIV_BEGINNT_HIER__$/ { print NR + 1; exit }' "$0")
tail -n +"$ZEILE" "$0" | base64 -d | tar -xz -C "$NEU" || fehler "Das Archiv im Installer ist beschädigt. Bitte neu herunterladen (git pull)."
[ -x "$NEU/etikettendruck/etikettendruck" ] || fehler "Das Archiv im Installer ist unvollständig."
rm -rf "$ZIEL.alt"
[ ! -d "$ZIEL" ] || mv "$ZIEL" "$ZIEL.alt"
mv "$NEU/etikettendruck" "$ZIEL"
rm -rf "$ZIEL.alt" "$NEU"
trap - EXIT

# 3. Startskript: nutzt die Gruppe lp sofort, auch ohne neues Anmelden
cat > "$ZIEL/starten.sh" <<'EOD'
#!/bin/sh
PROGRAMM="$(dirname "$(readlink -f "$0")")/etikettendruck"
if ! id -nG | tr ' ' '\n' | grep -qx lp \
   && getent group lp | cut -d: -f4 | tr ',' '\n' | grep -qx "$(id -un)"; then
    exec sg lp -c "'$PROGRAMM' $*"
fi
exec "$PROGRAMM" "$@"
EOD
chmod +x "$ZIEL/starten.sh"

cat > "$ZIEL/deinstallieren.sh" <<EOD
#!/bin/sh
# Entfernt das Programm. Eigene Daten (Produkte, Protokoll) in
# ${XDG_DATA_HOME:-$HOME/.local/share}/etikettendruck bleiben erhalten.
pkill -f "$ZIEL/etikettendruck" 2>/dev/null
rm -f "$ANWENDUNGEN/etikettendruck.desktop" "$SYMBOLE/etikettendruck.png" "$HOME/.local/bin/etikettendruck"
DESKTOP="\$(xdg-user-dir DESKTOP 2>/dev/null || echo "\$HOME/Desktop")"
rm -f "\$DESKTOP/etikettendruck.desktop"
rm -rf "$ZIEL"
echo "Etikettendruck entfernt. Eigene Daten liegen weiter in ${XDG_DATA_HOME:-$HOME/.local/share}/etikettendruck"
EOD
chmod +x "$ZIEL/deinstallieren.sh"

# 4. Startmenü, Schreibtisch, Kommandozeile
mkdir -p "$ANWENDUNGEN" "$SYMBOLE" "$HOME/.local/bin"
cp "$ZIEL/_internal/symbol.png" "$SYMBOLE/etikettendruck.png" 2>/dev/null || true
EINTRAG="[Desktop Entry]
Type=Application
Name=Etikettendruck
Comment=Etiketten mit Barcode und MHD auf dem Citizen drucken
Exec=\"$ZIEL/starten.sh\"
Icon=etikettendruck
Terminal=false
Categories=Office;
StartupNotify=false"
printf '%s\n' "$EINTRAG" > "$ANWENDUNGEN/etikettendruck.desktop"
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP" ]; then
    printf '%s\n' "$EINTRAG" > "$DESKTOP/etikettendruck.desktop"
    chmod +x "$DESKTOP/etikettendruck.desktop"
    # Cinnamon/GNOME: Verknüpfung als vertrauenswürdig markieren, sonst fragt der Schreibtisch nach
    gio set "$DESKTOP/etikettendruck.desktop" metadata::trusted true 2>/dev/null || true
fi
ln -sf "$ZIEL/starten.sh" "$HOME/.local/bin/etikettendruck"
update-desktop-database "$ANWENDUNGEN" 2>/dev/null || true

# 5. Druckrecht (Gruppe lp) – einmalig, braucht das Passwort
HINWEIS=""
if ! getent group lp | cut -d: -f4 | tr ',' '\n' | grep -qx "$(id -un)"; then
    if frage "Damit das Programm direkt auf den USB-Drucker schreiben darf, muss Ihr Benutzer einmalig in die Gruppe „lp“ aufgenommen werden. Dafür wird gleich Ihr Passwort abgefragt.

Jetzt einrichten?"; then
        if command -v pkexec >/dev/null 2>&1 && pkexec usermod -aG lp "$(id -un)"; then
            :
        elif [ -t 0 ] && sudo usermod -aG lp "$(id -un)"; then
            :
        else
            HINWEIS="

Achtung: Die Druckberechtigung konnte nicht eingerichtet werden. Im Terminal nachholen:
sudo usermod -aG lp $(id -un)"
        fi
    else
        HINWEIS="

Hinweis: Ohne die Gruppe „lp“ kann nicht direkt per USB gedruckt werden. Später im Terminal nachholen:
sudo usermod -aG lp $(id -un)"
    fi
fi

# 6. Starten
nohup "$ZIEL/starten.sh" >/dev/null 2>&1 &
info "Etikettendruck $VERSION ist installiert und startet jetzt im Browser.

Künftig starten über das Startmenü oder das Symbol „Etikettendruck“ auf dem Schreibtisch.
Eigene Produkte und das Druckprotokoll liegen in ${XDG_DATA_HOME:-$HOME/.local/share}/etikettendruck und bleiben bei Updates erhalten.$HINWEIS"
exit 0
__ARCHIV_BEGINNT_HIER__
