#!/bin/sh
# POINT D'ENTRÉE UNIQUE — Android (Termux), Linux, macOS :   sh INSTALLER.sh
cd "$(dirname "$0")/application" && exec sh installer.sh "$@"
