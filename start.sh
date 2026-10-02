#!/bin/sh
# Startet die Weboberfläche und öffnet den Browser.
cd "$(dirname "$0")" || exit 1
exec python3 -m etiketten start "$@"
