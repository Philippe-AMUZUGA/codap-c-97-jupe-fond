"""Prépare le dossier de roues pour l'installation hors ligne (à lancer une fois, avec accès au réseau).

Télécharge, pour chaque version de Python de la plage acceptée, les roues de toutes les bibliothèques
épinglées dans requirements.txt. Le dossier obtenu (par défaut vendor/wheels) n'entre jamais dans Git :
il est joint à la Release, une archive par plateforme. Au lancement, outils/amorce.py le détecte et
installe alors sans aucun accès au réseau.

Usage :  python outils/preparer_roues.py [-d dossier] [-p plateformes] [-v versions]
  -d  dossier de destination (défaut : vendor/wheels dans le dossier de l'application)
  -p  étiquettes de plateforme pip, séparées par des virgules (défaut : celles du système courant)
  -v  versions de Python, séparées par des virgules, par exemple 3.11,3.12 (défaut : la plage acceptée)

Seules des roues sont téléchargées (jamais de code à compiler). Les options de pip passent par les
variables d'environnement PIP_*. Code de sortie : 0 toutes les versions couvertes ; 1 couverture partielle,
la plage réellement couverte est affichée ; 2 aucune version couverte.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from amorce import lire_plage_python

PLATEFORMES = {
    "win32": "win_amd64",
    "linux": "manylinux2014_x86_64 manylinux_2_17_x86_64 manylinux_2_28_x86_64",
    "darwin": "macosx_11_0_arm64 macosx_11_0_universal2 macosx_10_9_x86_64 macosx_10_9_universal2",
}
ALERTE_OCTETS = 50 * 1024 * 1024
BLOCAGE_OCTETS = 100 * 1024 * 1024


def versions_de_la_plage(minimum, maximum):
    return ["%d.%d" % (minimum[0], m) for m in range(minimum[1], maximum[1] + 1)]


def plage_couverte(versions_ok):
    """Plus longue suite de versions mineures consécutives couvertes, ou None."""
    mineurs = sorted(int(v.split(".")[1]) for v in versions_ok)
    meilleure, courante = [], []
    for m in mineurs:
        courante = courante + [m] if courante and m == courante[-1] + 1 else [m]
        if len(courante) > len(meilleure):
            meilleure = courante
    if not meilleure:
        return None
    majeur = versions_ok[0].split(".")[0]
    return "%s.%d" % (majeur, meilleure[0]), "%s.%d" % (majeur, meilleure[-1])


def telecharger(dossier_app, destination, version, plateformes, env=None):
    """Une version de Python : un téléchargement pip. Rend (code, dernières lignes)."""
    environnement = dict(os.environ if env is None else env)
    environnement.update(
        {
            "PIP_ONLY_BINARY": ":all:",
            "PIP_PYTHON_VERSION": version.replace(".", ""),
            "PIP_IMPLEMENTATION": "cp",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
            "PIP_PROGRESS_BAR": "off",
            "PYTHONUTF8": "1",
        }
    )
    if plateformes:
        environnement["PIP_PLATFORM"] = plateformes.replace(",", " ")
    retour = subprocess.run(
        [sys.executable, "-m", "pip", "download", "-r", str(dossier_app / "requirements.txt"), "-d", str(destination)],
        env=environnement,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    fin = (retour.stdout + retour.stderr).strip().splitlines()[-4:]
    return retour.returncode, fin


def principal(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    options = {"-d": None, "-p": None, "-v": None}
    while arguments:
        cle = arguments.pop(0)
        if cle in options and arguments:
            options[cle] = arguments.pop(0)
        else:
            print(__doc__)
            return 2
    dossier_app = Path(__file__).resolve().parent.parent
    destination = Path(options["-d"]) if options["-d"] else dossier_app / "vendor" / "wheels"
    plateformes = options["-p"] or PLATEFORMES.get(sys.platform, "")
    minimum, maximum = lire_plage_python(dossier_app)
    versions = options["-v"].split(",") if options["-v"] else versions_de_la_plage(minimum, maximum)
    destination.mkdir(parents=True, exist_ok=True)
    print("Dossier des roues : %s" % destination)
    reussies, echouees = [], []
    for version in versions:
        print("Python %s : téléchargement des roues..." % version)
        code, fin = telecharger(dossier_app, destination, version, plateformes)
        if code == 0:
            reussies.append(version)
            print("  toutes les roues sont présentes pour Python %s." % version)
        else:
            echouees.append(version)
            print("  Python %s : roue manquante pour au moins une bibliothèque." % version)
            for ligne in fin:
                print("    " + ligne)
    roues = sorted(destination.glob("*.whl"))
    total = sum(f.stat().st_size for f in roues)
    print("%d roues, %.1f Mo au total." % (len(roues), total / 1048576))
    for roue in roues:
        taille = roue.stat().st_size
        if taille > BLOCAGE_OCTETS:
            print("BLOQUANT : %s dépasse 100 Mo (refusé par GitHub)." % roue.name)
        elif taille > ALERTE_OCTETS:
            print("Alerte : %s dépasse 50 Mo." % roue.name)
    couverte = plage_couverte(reussies) if reussies else None
    if couverte:
        print("Plage couverte : Python %s à %s." % couverte)
        print(
            "Si elle diffère de requires-python dans pyproject.toml, ajustez cette ligne (source unique de la plage)."
        )
    if not reussies:
        return 2
    return 0 if not echouees else 1


if __name__ == "__main__":
    sys.exit(principal())
