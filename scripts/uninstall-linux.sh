#!/bin/sh
set -eu

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
case "$data_home" in
    /*) ;;
    *) printf 'XDG_DATA_HOME must be an absolute path.\n' >&2; exit 1 ;;
esac
target="$data_home/pdftoolkit26"
desktop="$data_home/applications/org.pdftoolkit26.desktop"
[ ! -L "$target" ] && [ -f "$target/.pdftoolkit26-managed" ] || {
    printf 'No managed PDFtoolkit26 installation found; nothing was removed.\n' >&2
    exit 1
}
if [ -f "$desktop" ] && grep -Fqx '# Managed by PDFtoolkit26' "$desktop"; then rm -f -- "$desktop"; fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_home/applications" || :
fi
printf 'Removed PDFtoolkit26 from %s\n' "$target"
exec rm -rf -- "$target"
