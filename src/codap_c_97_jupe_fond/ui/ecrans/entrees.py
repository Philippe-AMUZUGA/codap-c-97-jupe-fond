"""Écran des entrées : le formulaire et le bouton de calcul."""

from __future__ import annotations

from tkinter import ttk

from ..panneaux import PanneauEntrees
from .base import Ecran

__all__ = ["EcranEntrees"]


class EcranEntrees(Ecran):
    CLE = "entrees"

    def construire(self, corps: ttk.Frame) -> None:
        panneau = PanneauEntrees(corps, self.app, avec_calcul=True)
        self.ajouter(panneau)
        self.formulaire = panneau.formulaire
