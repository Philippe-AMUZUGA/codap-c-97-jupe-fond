"""
Calcul sans interface : `python -m codap_c_97_jupe_fond.cli entrees.json [-o dossier]`.

Lit un fichier d'entrées, un projet enregistré ou le `projet.json` d'un export, valide (entrées structurées
comprises), calcule, puis affiche les mesures et, si un dossier est donné, écrit les fichiers d'export. C'est le
même noyau et la même validation que la fenêtre : une exécution rejoue un export. Options courtes seulement.
Codes de sortie : 0 réussi, 1 entrée ou export refusé.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path

from . import NOM, __version__
from .core import calculs, export
from .core.entrees import valider_entrees
from .core.erreurs import ErreurApplication, ErreurSaisie
from .core.fichiers import lire_entrees
from .textes import LANGUES, definir_langue, formater_nombre, t, t_sortie

__all__ = ["principal"]


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="codap_c_97_jupe_fond.cli",
        description=f"{NOM} : calcul depuis un fichier d'entrées, sans fenêtre.",
        add_help=False,
    )
    analyseur.add_argument("-h", action="help", help="affiche cette aide")
    analyseur.add_argument("entrees", help="fichier JSON d'entrées, ou projet.json d'un export")
    analyseur.add_argument("-o", dest="dossier", help="dossier où écrire les fichiers d'export")
    analyseur.add_argument(
        "-f", dest="formats", default=",".join(export.FORMATS), help="formats, séparés par des virgules"
    )
    analyseur.add_argument("-n", dest="nom", default="resultats", help="nom de base des fichiers exportés")
    analyseur.add_argument("-e", dest="ecraser", action="store_true", help="remplace les fichiers existants")
    analyseur.add_argument("-l", dest="langue", choices=LANGUES, help="langue des messages")
    analyseur.add_argument("-V", action="version", version=f"{NOM} {__version__}", help="affiche la version")
    return analyseur


def principal(argv: Sequence[str] | None = None) -> int:
    """Calcule depuis un fichier d'entrées ; rend le code de sortie."""
    with contextlib.suppress(AttributeError, OSError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    options = _analyseur().parse_args(argv)
    if options.langue:
        definir_langue(options.langue)
    try:
        entrees = valider_entrees(lire_entrees(options.entrees))
        resultat = calculs.calculer(entrees)
        for mesure in resultat.mesures:
            valeur = formater_nombre(mesure.valeur, 4) if isinstance(mesure.valeur, float) else str(mesure.valeur)
            print(f"{t_sortie(mesure.cle)} : {valeur} {mesure.unite}".rstrip())
        if options.dossier:
            formats = tuple(f.strip() for f in options.formats.split(",") if f.strip())
            ecrits = export.exporter(
                resultat, Path(options.dossier), nom=options.nom, formats=formats, ecraser=options.ecraser
            )
            print(t("export.fait", n=len(ecrits), dossier=options.dossier))
    except ErreurSaisie as erreur:
        for message in erreur.par_champ.values() or [str(erreur)]:  # toutes les entrées en défaut, une par ligne
            print(message, file=sys.stderr)
        return 1
    except ErreurApplication as erreur:
        print(str(erreur), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
