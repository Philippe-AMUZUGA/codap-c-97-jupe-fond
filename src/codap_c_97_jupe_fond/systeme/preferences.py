"""
Préférences de l'utilisateur : fichier JSON versionné, migré à la lecture, écrit d'un coup.

Un fichier illisible n'arrête pas l'application : il est mis de côté (`.corrompu`) et les valeurs par
défaut sont reprises. Un fichier plus récent que l'application est lu pour les clés connues.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .chemins import fichier_preferences

__all__ = [
    "FORMAT_ACTUEL",
    "NOMBRE_RECENTS",
    "TAILLE_MAX",
    "TAILLE_MIN",
    "Preferences",
    "ajouter_recent",
    "charger",
    "enregistrer",
    "migrer",
]

FORMAT_ACTUEL = 1
NOMBRE_RECENTS = 8
TAILLE_MIN, TAILLE_MAX = 80, 160
THEMES = ("clair", "sombre")
journal = logging.getLogger(__name__)


@dataclass
class Preferences:
    """Réglages gardés d'une séance à l'autre."""

    version_format: int = FORMAT_ACTUEL
    langue: str = ""
    theme: str = "clair"
    taille_police: int = 100
    journal_visible: bool = True
    journal_replie: bool = True  # replié sur sa dernière ligne : la zone centrale garde sa hauteur
    dossier_export: str = ""
    recents: list[str] = field(default_factory=list)


def migrer(brut: dict[str, Any]) -> dict[str, Any]:
    """Amène un contenu lu à la version courante du format (ajouter ici une étape par version)."""
    contenu = dict(brut)
    version = int(contenu.get("version_format", 0) or 0)
    if version < 1:  # avant le format 1 : la taille s'appelait `taille` et le thème `sombre` (booléen)
        if "taille" in contenu:
            contenu["taille_police"] = contenu.pop("taille")
        if "sombre" in contenu:
            contenu["theme"] = "sombre" if contenu.pop("sombre") else "clair"
    contenu["version_format"] = FORMAT_ACTUEL
    return contenu


def _assainir(prefs: Preferences) -> Preferences:
    """Ramène chaque valeur dans son domaine ; une valeur inattendue reprend son défaut."""
    defaut = Preferences()
    if prefs.theme not in THEMES:
        prefs.theme = defaut.theme
    if not isinstance(prefs.taille_police, int) or isinstance(prefs.taille_police, bool):
        prefs.taille_police = defaut.taille_police
    prefs.taille_police = max(TAILLE_MIN, min(TAILLE_MAX, prefs.taille_police))
    if not isinstance(prefs.langue, str):
        prefs.langue = defaut.langue
    if not isinstance(prefs.dossier_export, str):
        prefs.dossier_export = defaut.dossier_export
    prefs.journal_visible = bool(prefs.journal_visible)
    prefs.journal_replie = bool(prefs.journal_replie)
    recents = prefs.recents if isinstance(prefs.recents, list) else []
    prefs.recents = [str(r) for r in recents if isinstance(r, str)][:NOMBRE_RECENTS]
    return prefs


def charger(chemin: str | Path | None = None) -> Preferences:
    """Préférences enregistrées, ou les valeurs par défaut si le fichier manque ou ne se lit pas."""
    source = Path(chemin) if chemin else fichier_preferences()
    if not source.is_file():
        return Preferences()
    try:
        brut = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(brut, dict):
            raise ValueError("objet JSON attendu")
    except (OSError, ValueError) as erreur:
        journal.warning("préférences illisibles (%s) : valeurs par défaut reprises", erreur)
        with contextlib.suppress(OSError):
            os.replace(source, source.with_suffix(".json.corrompu"))
        return Preferences()
    noms = {f.name for f in fields(Preferences)}
    migre = migrer(brut)
    return _assainir(Preferences(**{k: v for k, v in migre.items() if k in noms}))


def enregistrer(prefs: Preferences, chemin: str | Path | None = None) -> Path:
    """Écrit les préférences (fichier provisoire puis remplacement) ; rend le chemin."""
    cible = Path(chemin) if chemin else fichier_preferences()
    cible.parent.mkdir(parents=True, exist_ok=True)
    provisoire = cible.with_name(cible.name + ".tmp")
    texte = json.dumps(asdict(_assainir(prefs)), ensure_ascii=False, indent=2)
    provisoire.write_text(texte + "\n", encoding="utf-8")
    os.replace(provisoire, cible)
    return cible


def ajouter_recent(prefs: Preferences, chemin: str | Path) -> None:
    """Met un fichier en tête des récents (sans doublon, huit au plus)."""
    texte = str(Path(chemin).resolve())
    prefs.recents = [texte, *(r for r in prefs.recents if r != texte)][:NOMBRE_RECENTS]
