"""
Chemins de l'application : données de l'utilisateur (hors du programme) et ressources livrées avec lui.

Données : `%APPDATA%/CodapC97JupeFond` (Windows), `~/Library/Application Support/CodapC97JupeFond` (macOS),
`$XDG_CONFIG_HOME/CodapC97JupeFond` ou `~/.config/CodapC97JupeFond` (Linux).
Journaux : `%LOCALAPPDATA%/CodapC97JupeFond/journaux` (Windows), `~/Library/Logs/CodapC97JupeFond` (macOS),
`$XDG_STATE_HOME/CodapC97JupeFond/journaux` ou `~/.local/state/CodapC97JupeFond/journaux` (Linux).
Le dossier du programme n'est jamais écrit.

Pour les essais, `rediriger(dossier)` (ou la variable d'environnement `VARIABLE_DONNEES`, le slug en
majuscules suivi de `_DONNEES`) range tout sous un dossier choisi : l'essai automatique et les tests ne
touchent pas aux données réelles.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .. import SLUG

__all__ = [
    "VARIABLE_DONNEES",
    "chemin_asset",
    "chemin_exemple",
    "dossier_donnees",
    "dossier_journaux",
    "dossier_paquet",
    "fichier_preferences",
    "ouvrir_dossier",
    "redirection",
    "rediriger",
]

VARIABLE_DONNEES = f"{SLUG.upper()}_DONNEES"
_redirection: Path | None = None


def rediriger(racine: str | Path | None) -> None:
    """Range données et journaux sous `racine` (None : retour aux dossiers du système)."""
    global _redirection
    _redirection = None if racine is None else Path(racine)


def redirection() -> Path | None:
    """Dossier de la redirection en cours (None : dossiers du système)."""
    return _redirection


def _racine_forcee() -> Path | None:
    if _redirection is not None:
        return _redirection
    valeur = os.environ.get(VARIABLE_DONNEES)
    return Path(valeur) if valeur else None


def _creer(dossier: Path, creer: bool) -> Path:
    if creer:
        dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def dossier_donnees(creer: bool = True) -> Path:
    """Dossier des préférences et des fichiers récents de l'utilisateur."""
    forcee = _racine_forcee()
    if forcee is not None:
        return _creer(forcee / "donnees", creer)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return _creer(base / SLUG, creer)


def dossier_journaux(creer: bool = True) -> Path:
    """Dossier des journaux (fichier roulant)."""
    forcee = _racine_forcee()
    if forcee is not None:
        return _creer(forcee / "journaux", creer)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / SLUG / "journaux"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs" / SLUG
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / SLUG / "journaux"
    return _creer(base, creer)


def fichier_preferences() -> Path:
    """Fichier JSON des préférences (le dossier est créé, pas le fichier)."""
    return dossier_donnees() / "preferences.json"


def dossier_paquet() -> Path:
    """Dossier du paquet installé ou du dépôt (lecture seule)."""
    return Path(__file__).resolve().parents[1]


def _racines_ressources() -> list[Path]:
    """Dossiers où chercher les ressources : exécutable autonome, paquet, dépôt, dossier courant."""
    paquet = dossier_paquet()
    candidats: list[Path] = []
    emballe = getattr(sys, "_MEIPASS", None)
    if emballe:
        candidats.append(Path(emballe))
    candidats += [paquet, paquet.parents[1], Path.cwd()]
    return candidats


def chemin_asset(nom: str) -> Path | None:
    """Chemin d'un fichier du dossier `assets` (icônes), ou None s'il manque."""
    for racine in _racines_ressources():
        for base in (racine / "assets", racine / "src" / "assets"):
            if (base / nom).is_file():
                return base / nom
    return None


def chemin_exemple() -> Path | None:
    """Fichier d'entrées de l'exemple (`examples/exemple.json`), ou None s'il manque."""
    for racine in _racines_ressources():
        for candidat in (racine / "examples" / "exemple.json", racine / "donnees" / "exemple.json"):
            if candidat.is_file():
                return candidat
    return None


def ouvrir_dossier(chemin: str | Path) -> bool:
    """Ouvre un dossier dans l'explorateur du système (sans shell) ; vrai si la demande est partie."""
    cible = str(chemin)
    try:
        if sys.platform == "win32":
            os.startfile(cible)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", cible])
        else:
            subprocess.Popen(["xdg-open", cible])
    except OSError:
        return False
    return True
