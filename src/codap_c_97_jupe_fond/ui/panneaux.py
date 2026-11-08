"""
Panneaux de l'interface : entrées, actions, résultats, export.

Un panneau est un morceau d'écran qui se suffit : le style « un écran » les range en deux colonnes
(`ecran_unique.py`), le style à rail les range chacun dans son écran (`ecrans/`). Aucun panneau
n'applique de règle : il lit ou demande à la fenêtre (`app`), qui lance les calculs dans un fil.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ..core.export import FORMATS
from ..core.resultat import Resultat
from ..textes import formater_nombre, t, t_sortie
from .formulaire import Formulaire
from .widgets import Colonne, Tableau, ZoneFigure, carte

if TYPE_CHECKING:
    from .app import Application

__all__ = ["Panneau", "PanneauActions", "PanneauEntrees", "PanneauExport", "PanneauResultats"]


class Panneau(ttk.Frame):
    """Socle des panneaux : garde la fenêtre et sait griser ses boutons pendant un calcul."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent)
        self.app = app
        self._boutons: list[ttk.Button] = []
        self.grid_columnconfigure(0, weight=1)

    def bouton(self, parent: tk.Misc, cle: str, commande: Any, *, principal: bool = False, **grille: Any) -> ttk.Button:
        """Bouton du panneau, actif seulement si aucun calcul ne tourne."""
        bouton = ttk.Button(parent, text=t(cle), command=commande, style="Accent.TButton" if principal else "TButton")
        if grille:
            bouton.grid(**grille)
        self._boutons.append(bouton)
        return bouton

    def basculer(self, occupe: bool) -> None:
        """Active ou grise les boutons pendant un calcul."""
        for bouton in self._boutons:
            bouton.configure(state="disabled" if occupe else "normal")

    def mettre_a_jour(self) -> None:
        """Relit l'état de la fenêtre (résultat, préférences) et met le panneau à jour."""


class PanneauEntrees(Panneau):
    """Le formulaire des entrées, avec de quoi reprendre les valeurs de l'exemple ou les défauts."""

    def __init__(self, parent: tk.Misc, app: Application, *, avec_calcul: bool = False) -> None:
        super().__init__(parent, app)
        self.formulaire = Formulaire(self, app.schema)
        self.formulaire.grid(row=0, column=0, sticky="ew")
        rangee = ttk.Frame(self)
        rangee.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.bouton(rangee, "entrees.defauts", app.valeurs_par_defaut, row=0, column=0, padx=(0, 8))
        self.bouton(rangee, "entrees.exemple", app.charger_exemple, row=0, column=1, padx=(0, 8))
        if avec_calcul:
            self.bouton(rangee, "actions.calculer", app.calculer, principal=True, row=0, column=2)

    def basculer(self, occupe: bool) -> None:
        super().basculer(occupe)
        self.formulaire.basculer(occupe)


class PanneauActions(Panneau):
    """Les actions principales : calculer, ouvrir et enregistrer des entrées, exporter."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent, app)
        cadre = carte(self, t("actions.titre"))
        cadre.grid(row=0, column=0, sticky="ew")
        cadre.grid_columnconfigure(0, weight=1)
        self.bouton(cadre, "actions.calculer", app.calculer, principal=True, row=0, column=0, sticky="ew", pady=(0, 8))
        self.bouton(cadre, "actions.ouvrir", app.ouvrir, row=1, column=0, sticky="ew", pady=(0, 8))
        self.bouton(cadre, "actions.enregistrer", app.enregistrer, row=2, column=0, sticky="ew", pady=(0, 8))
        self.bouton(cadre, "actions.exporter", app.exporter, row=3, column=0, sticky="ew")


class PanneauResultats(Panneau):
    """Mesures, tableaux et figures du dernier calcul."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent, app)
        self.vide = ttk.Label(self, text=t("resultats.vide"), style="Doux.TLabel")
        self.vide.grid(row=0, column=0, sticky="w")
        self.contenu = ttk.Frame(self)
        self.contenu.grid(row=1, column=0, sticky="ew")
        self.contenu.grid_columnconfigure(0, weight=1)
        self.tableaux: list[Tableau] = []
        self.figures: list[ZoneFigure] = []
        self.mesures: Tableau | None = None

    def effacer(self) -> None:
        for enfant in self.contenu.winfo_children():
            enfant.destroy()
        self.tableaux, self.figures, self.mesures = [], [], None
        self.vide.grid()

    def afficher(self, resultat: Resultat | None) -> None:
        """Remplace le contenu par les mesures, tableaux et figures du résultat."""
        self.effacer()
        if resultat is None:
            return
        self.vide.grid_remove()
        rang = 0
        cadre = carte(self.contenu, t("resultats.mesures"))
        cadre.grid(row=rang, column=0, sticky="ew")
        cadre.grid_columnconfigure(0, weight=1)
        colonnes: list[Colonne] = [
            ("mesure", t("export.col_mesure"), 260, "w"),
            ("valeur", t("export.col_valeur"), 140, "e"),
            ("unite", t("export.col_unite"), 90, "w"),
        ]
        self.mesures = Tableau(cadre, colonnes, hauteur=len(resultat.mesures))
        self.mesures.grid(row=0, column=0, sticky="ew")
        self.mesures.remplir((t_sortie(m.cle), _afficher(m.valeur), m.unite) for m in resultat.mesures)
        for tableau in resultat.tableaux:
            rang += 1
            cadre = carte(self.contenu, t_sortie(tableau.cle))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(10, 0))
            cadre.grid_columnconfigure(0, weight=1)
            colonnes = [(c, t_sortie(c), 150, "e") for c in tableau.colonnes]
            vue = Tableau(cadre, colonnes, hauteur=min(8, len(tableau.lignes)))
            vue.grid(row=0, column=0, sticky="ew")
            vue.remplir([_afficher(v) for v in ligne] for ligne in tableau.lignes)
            self.tableaux.append(vue)
        for figure in resultat.figures:
            rang += 1
            cadre = carte(self.contenu, t("resultats.figure"))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(10, 0))
            cadre.grid_columnconfigure(0, weight=1)
            zone = ZoneFigure(cadre, au_enregistrement=self.app.enregistrer_figure)
            zone.grid(row=0, column=0, sticky="ew")
            zone.afficher(figure)
            self.figures.append(zone)

    def mettre_a_jour(self) -> None:
        self.afficher(self.app.resultat)


def _afficher(valeur: Any) -> str:
    if isinstance(valeur, bool):
        return t("commun.oui") if valeur else t("commun.non")
    if isinstance(valeur, float):
        return formater_nombre(valeur, 4)
    return "" if valeur is None else str(valeur)


class PanneauExport(Panneau):
    """Choix des formats, du dossier et du nom de base, puis export du dernier résultat."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent, app)
        cadre = carte(self, t("export.titre"))
        cadre.grid(row=0, column=0, sticky="ew")
        cadre.grid_columnconfigure(1, weight=1)
        self.formats = {f: tk.BooleanVar(master=self, value=True) for f in FORMATS}
        for rang, nom in enumerate(FORMATS):
            ttk.Checkbutton(cadre, text=t(f"export.format_{nom}"), variable=self.formats[nom]).grid(
                row=rang, column=0, columnspan=3, sticky="w"
            )
        ttk.Label(cadre, text=t("export.dossier"), style="Carte.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        self.dossier = tk.StringVar(master=self, value=app.prefs.dossier_export or str(Path.home()))
        ttk.Entry(cadre, textvariable=self.dossier).grid(row=5, column=0, columnspan=2, sticky="ew", padx=(0, 8))
        self.bouton(cadre, "export.parcourir", self.choisir_dossier, row=5, column=2)
        ttk.Label(cadre, text=t("export.nom"), style="Carte.TLabel").grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        self.nom = tk.StringVar(master=self, value="")
        ttk.Entry(cadre, textvariable=self.nom).grid(row=7, column=0, columnspan=3, sticky="ew")
        rangee = ttk.Frame(cadre, style="Carte.TFrame")
        rangee.grid(row=8, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self.bouton(rangee, "export.lancer", self.lancer, principal=True, row=0, column=0, padx=(0, 8))
        self.bouton(rangee, "export.ouvrir_dossier", self.ouvrir_dossier, row=0, column=1)
        self.etat = ttk.Label(cadre, text="", style="CarteDoux.TLabel")
        self.etat.grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def formats_choisis(self) -> tuple[str, ...]:
        return tuple(f for f, variable in self.formats.items() if variable.get())

    def choisir_dossier(self) -> None:
        choix = self.app.dialogues.choisir_dossier(t("export.choisir"), self.dossier.get())
        if choix:
            self.dossier.set(choix)

    def parametres(self) -> dict[str, Any]:
        """Dossier, nom de base et formats choisis, tels que `Application.exporter` les attend."""
        return {
            "dossier": self.dossier.get().strip(),
            "nom": self.nom.get().strip() or None,
            "formats": self.formats_choisis(),
        }

    def lancer(self) -> None:
        self.app.exporter(**self.parametres())

    def ouvrir_dossier(self) -> None:
        self.app.ouvrir_dossier_export(self.dossier.get().strip())

    def mettre_a_jour(self) -> None:
        if not self.nom.get() and self.app.resultat is not None:
            self.nom.set(self.app.nom_de_base())
        fichiers = self.app.derniers_fichiers
        self.etat.configure(text=t("export.derniers", n=len(fichiers)) if fichiers else "")
