"""Ce que rend un calcul : mesures, tableaux et figures, sans aucune dépendance d'interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Mesure", "Resultat", "TableauResultat"]


@dataclass(frozen=True)
class Mesure:
    """Une valeur de sortie : clé de texte (`sortie.<cle>`), valeur et unité."""

    cle: str
    valeur: float | int | str | bool
    unite: str = ""


@dataclass(frozen=True)
class TableauResultat:
    """Un tableau de sortie : clé de texte du titre, clés de texte des colonnes, lignes de valeurs."""

    cle: str
    colonnes: tuple[str, ...]
    lignes: tuple[tuple[Any, ...], ...]


@dataclass
class Resultat:
    """Résultat complet d'un calcul.

    `figures` contient des figures matplotlib (`matplotlib.figure.Figure`, sans pyplot) ; le noyau ne les
    affiche jamais, l'interface les pose dans une zone et l'export les enregistre.
    """

    entrees: dict[str, Any]
    mesures: tuple[Mesure, ...] = ()
    tableaux: tuple[TableauResultat, ...] = ()
    figures: tuple[Any, ...] = field(default=(), compare=False)

    def mesure(self, cle: str) -> Mesure:
        """La mesure de cette clé ; `KeyError` si elle manque."""
        for mesure in self.mesures:
            if mesure.cle == cle:
                return mesure
        raise KeyError(cle)
