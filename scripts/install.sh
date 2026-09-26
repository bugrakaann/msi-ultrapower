#!/usr/bin/env bash
# ~/.local/bin altına pil-modu ve pil-modu-ui başlatıcılarını kurar.
# Kod bu klasörde kalır; başlatıcılar yalnızca buradaki "src" klasörünü kullanır.
# Yani kodu düzenledikten sonra yeniden kurman gerekmez.
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${BIN:-$HOME/.local/bin}"
APPS="${APPS:-$HOME/.local/share/applications}"
mkdir -p "$BIN" "$APPS"

launcher() {  # launcher <dosya adı> <modül>
    cat > "$BIN/$1" <<PY
#!/usr/bin/python3
# pil-modu başlatıcısı: $PROJECT/scripts/install.sh tarafından oluşturuldu.
import sys
sys.path.insert(0, "$PROJECT/src")
from $2 import main
sys.exit(main())
PY
    chmod 755 "$BIN/$1"
    echo "Kuruldu: $BIN/$1"
}

launcher pil-modu pil_modu.cli
launcher pil-modu-ui pil_modu.ui.app

sed "s|@BIN@|$BIN|g" "$PROJECT/data/pil-modu-ui.desktop" > "$APPS/pil-modu-ui.desktop"
echo "Kuruldu: $APPS/pil-modu-ui.desktop"
