"""
Formulaire généré depuis le schéma des entrées : un champ par paramètre, groupé en cartes.

Chaque champ a son libellé, son unité, son aide et un emplacement pour le message d'erreur, juste dessous.
Le formulaire n'applique aucune règle : `valider` appelle `core.schema.valider`, la même validation que la
ligne de commande, et marque les champs en défaut d'un coup. Une entrée de type `tableau` est saisie dans une
grille (`widgets.GrilleSaisie`) : une rangée par ligne, des boutons pour en ajouter ou en retirer. Une entrée
marquée `formulaire = false` n'est pas dessinée ici : un écran dédié la saisit (voir `ecrans/base.py`).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from tkinter import ttk
from typing import Any

from ..core.erreurs import ErreurSaisie
from ..core.schema import Champ, valider, valider_champ
from ..textes import formater_nombre, langue, t
from .widgets import GrilleSaisie, carte

__all__ = ["Formulaire"]

LARGEUR_SAISIE = 18
LARGEUR_CHOIX = 34


class Formulaire(ttk.Frame):
    """Saisie des entrées. `brut()` donne les textes saisis, `valider()` les valeurs typées."""

    def __init__(
        self,
        parent: tk.Misc,
        champs: tuple[Champ, ...],
        *,
        au_changement: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.champs = tuple(c for c in champs if c.formulaire)
        self._langue = langue()
        self._au_changement = au_changement
        self.variables: dict[str, tk.Variable] = {}
        self.grilles: dict[str, GrilleSaisie] = {}
        self.widgets: dict[str, tk.Widget] = {}
        self._infos: dict[str, ttk.Label] = {}
        self._etiquettes: dict[str, dict[str, str]] = {}  # nom du champ, puis texte affiché vers valeur
        self.grid_columnconfigure(0, weight=1)
        self._construire()
        self.definir({c.nom: c.defaut for c in self.champs if c.defaut is not None})

    # Construction
    def _construire(self) -> None:
        groupes: dict[str, list[Champ]] = {}
        for champ in self.champs:
            groupes.setdefault(champ.groupe_dans(self._langue), []).append(champ)
        for rang, (titre, membres) in enumerate(groupes.items()):
            cadre = carte(self, titre or t("formulaire.titre"))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(0 if rang == 0 else 10, 0))
            cadre.grid_columnconfigure(2, weight=1)  # l'unité se place contre la saisie, la place libre est à droite
            cadre.bind("<Configure>", lambda e, c=cadre: self._adapter_les_aides(c, e.width), add="+")
            for k, champ in enumerate(membres):
                self._ligne(cadre, 2 * k, champ)

    def _adapter_les_aides(self, cadre: ttk.LabelFrame, largeur: int) -> None:
        """Les textes d'aide passent à la ligne selon la largeur de la carte, à partir de la colonne des saisies."""
        debut = cadre.grid_bbox(column=1, row=0)[0]
        for info in self._infos.values():
            if info.master is cadre:
                info.configure(wraplength=max(160, largeur - debut - 40))

    def _ligne(self, cadre: ttk.LabelFrame, ligne: int, champ: Champ) -> None:
        ttk.Label(cadre, text=champ.libelle_dans(self._langue), style="Carte.TLabel").grid(
            row=ligne, column=0, sticky="w", padx=(0, 12), pady=(6, 0)
        )
        saisie = self._saisie(cadre, champ)
        etendue = champ.type == "texte" and not champ.unite
        saisie.grid(row=ligne, column=1, columnspan=2 if etendue else 1, sticky="ew" if etendue else "w", pady=(6, 0))
        self.widgets[champ.nom] = saisie
        if champ.unite:
            ttk.Label(cadre, text=champ.unite, style="CarteDoux.TLabel").grid(
                row=ligne, column=2, sticky="w", padx=(8, 0), pady=(6, 0)
            )
        info = ttk.Label(cadre, text=champ.aide_dans(self._langue), style="CarteDoux.TLabel", justify="left")
        info.grid(row=ligne + 1, column=1, columnspan=2, sticky="w")
        self._infos[champ.nom] = info

    def _saisie(self, cadre: ttk.LabelFrame, champ: Champ) -> tk.Widget:
        if champ.type == "tableau":
            grille = GrilleSaisie(
                cadre,
                champ.colonnes,
                self._langue,
                lignes_min=champ.lignes_min,
                lignes_max=champ.lignes_max,
                au_changement=self._a_change,
            )
            self.grilles[champ.nom] = grille
            return grille
        if champ.type == "booleen":
            variable: tk.Variable = tk.BooleanVar(master=self)
            saisie: tk.Widget = ttk.Checkbutton(cadre, variable=variable)
        elif champ.type == "choix":
            etiquettes = {champ.etiquette_dans(v, self._langue): v for v in champ.choix}
            self._etiquettes[champ.nom] = etiquettes
            variable = tk.StringVar(master=self)
            saisie = ttk.Combobox(
                cadre, textvariable=variable, values=list(etiquettes), state="readonly", width=LARGEUR_CHOIX
            )
        elif champ.type == "entier" and champ.minimum is not None and champ.maximum is not None:
            variable = tk.StringVar(master=self)
            saisie = ttk.Spinbox(
                cadre,
                textvariable=variable,
                from_=champ.minimum,
                to=champ.maximum,
                increment=1,
                width=LARGEUR_SAISIE - 2,
            )
        else:
            variable = tk.StringVar(master=self)
            largeur = LARGEUR_CHOIX if champ.type == "texte" else LARGEUR_SAISIE
            saisie = ttk.Entry(cadre, textvariable=variable, width=largeur)
        self.variables[champ.nom] = variable
        variable.trace_add("write", lambda *_: self._a_change())
        saisie.bind("<FocusOut>", lambda _e, nom=champ.nom: self.verifier_champ(nom), add="+")
        return saisie

    def _a_change(self) -> None:
        if self._au_changement is not None:
            self._au_changement()

    # Valeurs
    def brut(self) -> dict[str, Any]:
        """Valeurs saisies, avant validation (textes, booléens, valeurs de choix)."""
        valeurs: dict[str, Any] = {}
        for champ in self.champs:
            if champ.type == "tableau":
                valeurs[champ.nom] = self.grilles[champ.nom].brut()
                continue
            saisi = self.variables[champ.nom].get()
            if champ.type == "choix":
                saisi = self._etiquettes[champ.nom].get(saisi, saisi)
            valeurs[champ.nom] = saisi
        return valeurs

    def definir(self, valeurs: Mapping[str, Any]) -> None:
        """Remplit les champs connus (un nom inconnu est ignoré ; la validation dira le reste)."""
        for champ in self.champs:
            if champ.nom not in valeurs:
                continue
            valeur = valeurs[champ.nom]
            if champ.type == "tableau":
                self.grilles[champ.nom].definir(valeur if isinstance(valeur, list | tuple) else ())
                continue
            variable = self.variables[champ.nom]
            if champ.type == "booleen":
                variable.set(bool(valeur))
            elif champ.type == "choix":
                variable.set(champ.etiquette_dans(str(valeur), self._langue))
            elif champ.type == "reel" and isinstance(valeur, int | float) and not isinstance(valeur, bool):
                variable.set(formater_nombre(float(valeur)))
            else:
                variable.set("" if valeur is None else str(valeur))
        self.effacer_erreurs()

    def valider(self) -> dict[str, Any]:
        """Valeurs typées de tous les champs ; marque les champs en défaut et relève `ErreurSaisie`."""
        self.effacer_erreurs()
        try:
            return valider(self.champs, self.brut())
        except ErreurSaisie as erreur:
            self.marquer_erreurs(erreur.par_champ)
            raise

    def verifier_champ(self, nom: str) -> None:
        """Vérifie un seul champ (à la sortie du champ) et marque ou efface son message."""
        champ = next((c for c in self.champs if c.nom == nom), None)
        if champ is None:
            return
        try:
            valider_champ(champ, self.brut()[nom])
        except ErreurSaisie as erreur:
            self.marquer_erreurs({nom: str(erreur)})
        else:
            self._montrer_info(nom, None)

    # Messages
    def marquer_erreurs(self, par_champ: Mapping[str, str]) -> None:
        """Affiche le message de chaque champ en défaut, sous le champ."""
        for nom, message in par_champ.items():
            self._montrer_info(nom, message)

    def effacer_erreurs(self) -> None:
        for nom in self._infos:
            self._montrer_info(nom, None)

    def _montrer_info(self, nom: str, erreur: str | None) -> None:
        info = self._infos.get(nom)
        champ = next((c for c in self.champs if c.nom == nom), None)
        if info is None or champ is None:
            return
        if erreur:
            info.configure(text=erreur, style="CarteErreur.TLabel")
        else:
            info.configure(text=champ.aide_dans(self._langue), style="CarteDoux.TLabel")

    def message(self, nom: str) -> str:
        """Texte affiché sous un champ, aide ou erreur (pour les tests)."""
        return str(self._infos[nom].cget("text"))

    def basculer(self, occupe: bool) -> None:
        """Grise les saisies pendant un calcul."""
        for champ in self.champs:
            if champ.type == "tableau":
                self.grilles[champ.nom].basculer(occupe)
                continue
            widget = self.widgets[champ.nom]
            etat = "readonly" if champ.type == "choix" else "normal"
            widget.configure(state="disabled" if occupe else etat)
