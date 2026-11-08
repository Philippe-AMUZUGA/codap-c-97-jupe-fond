"""Lance l'application : `python -m codap_c_97_jupe_fond` ; l'option `-t` rejoue un essai complet, sans geste."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import sys
from collections.abc import Sequence

from . import DESCRIPTION, NOM, PYTHON_MIN, __version__
from .textes import t

MODULES_REQUIS = ("tkinter", "matplotlib", "openpyxl")


def _analyseur() -> argparse.ArgumentParser:
    """Options courtes seulement : `-t` essai, `-s` dossier de l'essai, `-v` journal en console, `-V` version."""
    analyseur = argparse.ArgumentParser(
        prog="codap_c_97_jupe_fond", description=f"{NOM} : {DESCRIPTION}", add_help=False
    )
    analyseur.add_argument("-h", action="help", help="affiche cette aide")
    analyseur.add_argument("-V", action="version", version=f"{NOM} {__version__}", help="affiche la version")
    analyseur.add_argument(
        "-t",
        dest="essai",
        action="store_true",
        help="essai automatique : ouvre la fenêtre, mène l'exemple jusqu'à l'export, puis la ferme",
    )
    analyseur.add_argument(
        "-s", dest="sortie", help="avec -t : dossier où garder l'export (sinon un dossier temporaire, effacé)"
    )
    analyseur.add_argument("-v", dest="verbeux", action="store_true", help="écrit aussi le journal dans la console")
    return analyseur


def _dire(texte: str) -> None:
    """Écrit sur la sortie standard si elle existe (une application sans console n'en a pas)."""
    with contextlib.suppress(AttributeError, OSError, ValueError):
        print(texte)


def _version(texte: str) -> tuple[int, ...]:
    return tuple(int(n) for n in texte.split("."))


def modules_manquants() -> list[str]:
    """Bibliothèques nécessaires à l'application que ce Python ne trouve pas."""
    return [nom for nom in MODULES_REQUIS if importlib.util.find_spec(nom) is None]


def verifier_poste() -> str | None:
    """Le motif, en clair, pour lequel l'application ne peut pas démarrer ; None si tout est prêt."""
    if sys.version_info[:2] < _version(PYTHON_MIN):
        trouve = f"{sys.version_info[0]}.{sys.version_info[1]}"
        return t("poste.python_ancien", minimum=PYTHON_MIN, trouve=trouve)
    manquants = modules_manquants()
    if "tkinter" in manquants:
        return t("poste.tk")
    if manquants:
        return t("poste.modules", liste=", ".join(manquants))
    return None


def principal(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée : sans option, ouvre l'application ; avec -t, l'essai automatique."""
    for flux in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            flux.reconfigure(encoding="utf-8", errors="replace")
    options = _analyseur().parse_args(argv)
    motif = verifier_poste()
    if motif is not None:
        _dire(motif)
        return 1
    if options.essai:
        from .essai import essai_automatique

        return essai_automatique(options.sortie, _dire)
    from .systeme import journal
    from .ui.app import lancer

    flux = journal.installer(console=options.verbeux)
    journal.poser_crochets()
    lancer(flux)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
