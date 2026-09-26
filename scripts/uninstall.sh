#!/usr/bin/env bash
# Başlatıcıları kaldırır. Durum dosyalarına (~/.local/share/pil-modu) ve
# sistem ayarlarına dokunmaz; önce "pil-modu geri" çalıştırman önerilir.
set -euo pipefail
BIN="${BIN:-$HOME/.local/bin}"
APPS="${APPS:-$HOME/.local/share/applications}"
rm -fv "$BIN/pil-modu" "$BIN/pil-modu-ui" "$APPS/pil-modu-ui.desktop"
