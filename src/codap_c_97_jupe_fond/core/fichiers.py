"""
Fichiers d'entrées et projets enregistrés : lecture et écriture d'un JSON, avec contrôle de taille et de forme.

Un fichier d'entrées est un objet JSON dont les clés sont les noms du schéma. Le fichier écrit par
l'application (le projet enregistré) porte en plus `version_format`, les entrées sous la clé `entrees` (entrées
structurées comprises : tableaux de lignes) et, sous la clé `etat`, ce que les écrans gardent d'une séance à
l'autre (un choix, des valeurs saisies après le calcul, le fait qu'un calcul avait abouti). Le `projet.json` d'un
export contient les mêmes entrées sous la clé `entrees` et se rouvre de la même façon.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .erreurs import ErreurSaisie

__all__ = ["FORMAT_ENTREES", "TAILLE_MAX_OCTETS", "ecrire_entrees", "ecrire_projet", "lire_entrees", "lire_projet"]

FORMAT_ENTREES = 2  # 1 : entrées seules ; 2 : entrées et état des écrans
TAILLE_MAX_OCTETS = 1_000_000


def _lire_objet(source: Path) -> dict[str, Any]:
    try:
        if source.stat().st_size > TAILLE_MAX_OCTETS:
            raise ErreurSaisie("fichier.trop_gros", nom=source.name, maximum=TAILLE_MAX_OCTETS // 1000)
        contenu = json.loads(source.read_text(encoding="utf-8-sig"))
    except OSError:
        raise ErreurSaisie("fichier.illisible", nom=source.name) from None
    except ValueError:
        raise ErreurSaisie("fichier.pas_json", nom=source.name) from None
    if not isinstance(contenu, dict):
        raise ErreurSaisie("fichier.pas_objet", nom=source.name)
    return contenu


def lire_projet(chemin: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Entrées brutes (à passer ensuite à la validation) et état des écrans d'un fichier enregistré.

    Accepte un objet plat (entrées seules), un objet `{"version_format": n, "entrees": {...}, "etat": {...}}` ou un
    `projet.json` d'export ; l'état manque dans les deux premiers cas et vaut alors `{}`.
    """
    source = Path(chemin)
    contenu = _lire_objet(source)
    if not isinstance(contenu.get("entrees"), dict):
        return contenu, {}
    etat = contenu.get("etat", {})
    if not isinstance(etat, dict):
        raise ErreurSaisie("fichier.etat_invalide", nom=source.name)
    return contenu["entrees"], etat


def lire_entrees(chemin: str | Path) -> dict[str, Any]:
    """Valeurs brutes d'un fichier d'entrées ou d'un projet (à passer ensuite à la validation)."""
    return lire_projet(chemin)[0]


def ecrire_projet(chemin: str | Path, valeurs: dict[str, Any], etat: dict[str, Any] | None = None) -> Path:
    """Écrit des entrées validées et l'état des écrans (fichier provisoire puis remplacement)."""
    cible = Path(chemin)
    provisoire = cible.with_name(cible.name + ".tmp")
    corps = {"version_format": FORMAT_ENTREES, "entrees": valeurs, "etat": dict(etat or {})}
    try:
        provisoire.write_text(json.dumps(corps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        provisoire.replace(cible)
    finally:
        provisoire.unlink(missing_ok=True)
    return cible


def ecrire_entrees(chemin: str | Path, valeurs: dict[str, Any]) -> Path:
    """Écrit des entrées validées, sans état d'écran."""
    return ecrire_projet(chemin, valeurs)
