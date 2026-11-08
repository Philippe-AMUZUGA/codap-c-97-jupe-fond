"""Écran des résultats : mesures, tableaux et figures du dernier calcul."""

from __future__ import annotations

from tkinter import ttk

from ..panneaux import PanneauResultats
from .base import Ecran

__all__ = ["EcranResultats"]


class EcranResultats(Ecran):
    CLE = "resultats"
    EXIGE_RESULTAT = True

    def construire(self, corps: ttk.Frame) -> None:
        self.panneau = PanneauResultats(corps, self.app)
        self.ajouter(self.panneau)
