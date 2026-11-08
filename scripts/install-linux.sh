#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
case "$data_home" in
    /*) ;;
    *) printf 'XDG_DATA_HOME must be an absolute path.\n' >&2; exit 1 ;;
esac
case "$data_home" in
    *'
'*) printf 'The installation path cannot contain a newline.\n' >&2; exit 1 ;;
    *'='*) printf 'The installation path cannot contain an equals sign.\n' >&2; exit 1 ;;
    *"$(printf '\t')"*|*"$(printf '\r')"*) printf 'The installation path cannot contain tabs or carriage returns.\n' >&2; exit 1 ;;
esac

target="$data_home/pdftoolkit26"
desktop="$data_home/applications/org.pdftoolkit26.desktop"
[ -f "$source_dir/PDFtoolkit26" ] && [ -f "$source_dir/_internal/deskpdf/assets/icon.png" ] || {
    printf 'Run this installer from the extracted PDFtoolkit26 folder.\n' >&2
    exit 1
}
[ ! -L "$target" ] || { printf 'The installation folder is a symlink; leaving it untouched.\n' >&2; exit 1; }
if [ -e "$target" ] && [ ! -f "$target/.pdftoolkit26-managed" ]; then
    printf 'The installation folder already exists and is not managed by PDFtoolkit26.\n' >&2
    exit 1
fi
[ ! -L "$desktop" ] || { printf 'The application shortcut is a symlink; leaving it untouched.\n' >&2; exit 1; }
if [ -e "$desktop" ] && ! grep -Fqx '# Managed by PDFtoolkit26' "$desktop"; then
    printf 'An application shortcut already exists; leaving it untouched.\n' >&2
    exit 1
fi
[ "$source_dir" != "$target" ] || { printf 'PDFtoolkit26 is already installed.\n'; exit 0; }
mkdir -p "$data_home" "$data_home/applications"
stage=$(mktemp -d "$data_home/.pdftoolkit26-new.XXXXXXXX")
backup=
cleanup() {
    [ -z "$stage" ] || rm -rf -- "$stage"
    if [ -n "$backup" ] && [ ! -e "$target" ]; then mv -- "$backup" "$target"; fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
cp -a "$source_dir/." "$stage/"
printf 'PDFtoolkit26 managed installation\n' > "$stage/.pdftoolkit26-managed"
if [ -e "$target" ]; then
    backup=$(mktemp -d "$data_home/.pdftoolkit26-old.XXXXXXXX")
    rmdir -- "$backup"
    mv -- "$target" "$backup"
fi
mv -- "$stage" "$target"
stage=
if [ -n "$backup" ]; then rm -rf -- "$backup"; backup=; fi

escape_exec() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\$/\\$/g; s/`/\\`/g; s/%/%%/g' | sed 's/\\/\\\\/g'; }
escape_value() { printf '%s' "$1" | sed 's/\\/\\\\/g'; }
command_path=$(escape_exec "$target/PDFtoolkit26")
icon_path=$(escape_value "$target/_internal/deskpdf/assets/icon.png")
cat > "$desktop" <<EOF
[Desktop Entry]
# Managed by PDFtoolkit26
Type=Application
Name=PDFtoolkit26
Comment=Edit, organize and convert PDF files
Exec="$command_path" %F
Icon=$icon_path
Terminal=false
Categories=Office;Graphics;
MimeType=application/pdf;
EOF
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_home/applications" || :
fi
printf 'Installed PDFtoolkit26 to %s\n' "$target"
printf 'Open it from your application menu, or run %s/PDFtoolkit26\n' "$target"
