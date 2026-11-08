"""Écran d'export : formats, dossier, nom de base et lancement."""

from __future__ import annotations

from tkinter import ttk

from ..panneaux import PanneauExport
from .base import Ecran

__all__ = ["EcranExport"]


class EcranExport(Ecran):
    CLE = "export"
    EXIGE_RESULTAT = True

    def construire(self, corps: ttk.Frame) -> None:
        self.panneau = PanneauExport(corps, self.app)
        self.ajouter(self.panneau)

    def accompli(self) -> bool:
        """L'export est fait quand le dernier résultat a été écrit."""
        return bool(self.app.derniers_fichiers)
