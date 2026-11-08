#!/bin/sh
# Lanceur Linux et macOS. Trouve un Python accepté (64 bits) dans la plage de l'application,
# puis appelle outils/amorce.py, qui prépare l'environnement local, installe au premier lancement
# et lance l'application. Ce script n'utilise jamais sudo et ne modifie aucun réglage du système.
cd "$(dirname "$0")" || exit 1
PYTHONUTF8=1
export PYTHONUTF8
PY_MIN="3.11"
PY_MAX="3.13"
MAJ="${PY_MAX%%.*}"
MAX_MIN="${PY_MAX#*.}"
MIN_MIN="${PY_MIN#*.}"

# accepte PYTHON [tk] : dans la plage, 64 bits ; avec « tk », qui charge aussi Tk (la fenêtre en a besoin)
accepte() {
    imports="import sys,struct"
    if [ "$2" = "tk" ]; then
        imports="import sys,struct,tkinter; tkinter.Tcl().eval('info patchlevel')"
    fi
    "$1" -c "${imports}; sys.exit(0 if (${MAJ},${MIN_MIN}) <= sys.version_info[:2] <= (${MAJ},${MAX_MIN}) and struct.calcsize('P')==8 else 1)" >/dev/null 2>&1
}

# chercher [tk] : le Python le plus haut de la plage, puis python3
chercher() {
    PY=""
    m="$MAX_MIN"
    while [ -z "$PY" ] && [ "$m" -ge "$MIN_MIN" ]; do
        if command -v "python${MAJ}.${m}" >/dev/null 2>&1 && accepte "python${MAJ}.${m}" "$1"; then
            PY="python${MAJ}.${m}"
        fi
        m=$((m - 1))
    done
    if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1 && accepte python3 "$1"; then
        PY="python3"
    fi
}

# premier passage avec Tk ; second sans l'exigence de Tk, pour que amorce.py dise précisément l'absence de Tk (code 11)
chercher tk
if [ -z "$PY" ]; then
    chercher
fi

if [ -z "$PY" ]; then
    printf '\n'
    printf "CODAP C9.7 Jupe-Fond a besoin de Python %s à %s (64 bits) et ne l'a pas trouvé.\n" "$PY_MIN" "$PY_MAX"
    printf '\n'
    printf "Debian et Ubuntu : installez, ou demandez à l'administrateur d'installer, les paquets\n"
    printf '    python3  python3-venv  python3-tk\n'
    printf 'Fedora : python3  python3-tkinter.   macOS : Python depuis https://www.python.org/downloads/\n'
    printf 'ou, avec Homebrew, le paquet python-tk.\n'
    printf '\n'
    printf "Ce lanceur ne lance jamais sudo à votre place. Relancez-le une fois Python installé.\n"
    exit 10
fi

exec "$PY" outils/amorce.py "$@"
