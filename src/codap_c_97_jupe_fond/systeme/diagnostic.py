"""
Diagnostic à copier dans un signalement d'anomalie : version, système, réglages et fin du journal.

Le dossier personnel de l'utilisateur est remplacé par `~` partout, pour qu'un signalement public ne
révèle ni son nom de compte ni l'arborescence de son poste.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import asdict
from pathlib import Path

from .. import NOM, SLUG, __version__
from ..textes import langue
from . import journal
from .preferences import Preferences

__all__ = ["anonymiser", "diagnostic"]


def anonymiser(texte: str) -> str:
    """Remplace le dossier personnel (avec ses deux écritures de séparateurs) et le nom du compte par `~`."""
    accueil = str(Path.home())
    for forme in {accueil, accueil.replace("\\", "/"), accueil.replace("/", "\\")}:
        if forme:
            texte = texte.replace(forme, "~")
    return texte


def diagnostic(prefs: Preferences | None = None, version_tk: str = "", lignes: int = 40) -> str:
    """Texte de diagnostic prêt à coller dans un signalement (jamais de donnée de l'utilisateur)."""
    corps = [
        f"{NOM} ({SLUG}) {__version__}",
        f"Python {platform.python_version()} ({platform.architecture()[0]}), {platform.platform()}",
        f"Tk {version_tk or '?'}, langue {langue()}",
    ]
    if prefs is not None:
        reglages = asdict(prefs)
        reglages.pop("recents", None)
        reglages.pop("dossier_export", None)
        corps.append("Réglages : " + ", ".join(f"{k}={v}" for k, v in reglages.items()))
    corps.append(f"Exécutable : {sys.executable}")
    corps.append("=== journal (dernières lignes) ===")
    corps += journal.lignes_recentes(lignes) or ["(journal vide)"]
    return anonymiser("\n".join(corps))
