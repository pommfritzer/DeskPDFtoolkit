#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python=${PYTHON:-python3}
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-offscreen}
"$python" scripts/make_icon.py
"$python" -m pytest -q
"$python" scripts/collect_licenses.py
"$python" -m PyInstaller --noconfirm --clean PDFtoolkit26.spec
"$python" scripts/check_bundle.py
version=$("$python" -c 'from deskpdf import __version__; print(__version__)')
mkdir -p releases
case "$(uname -s)" in
    Linux)
        cp scripts/install-linux.sh dist/PDFtoolkit26/install.sh
        cp scripts/uninstall-linux.sh dist/PDFtoolkit26/uninstall.sh
        chmod +x dist/PDFtoolkit26/install.sh dist/PDFtoolkit26/uninstall.sh
        tar -C dist -czf "releases/PDFtoolkit26-${version}-linux-$(uname -m).tar.gz" PDFtoolkit26
        ;;
    Darwin)
        ditto -c -k --sequesterRsrc --keepParent dist/PDFtoolkit26.app "releases/PDFtoolkit26-${version}-macos-$(uname -m).zip"
        ;;
    *)
        printf 'Unsupported platform: %s\n' "$(uname -s)" >&2
        exit 1
        ;;
esac
