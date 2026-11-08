"""Socle commun des écrans : titre, trois repères d'aide, corps défilant, panneaux gérés, verrou et saisie propres."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ...textes import t
from ..formulaire import Formulaire
from ..panneaux import Panneau
from ..widgets import ScrollableFrame, aide_de_l_ecran

if TYPE_CHECKING:
    from ..app import Application

__all__ = ["Ecran"]


class Ecran(ttk.Frame):
    """Un écran du rail : relit l'état de la fenêtre à chaque affichage, n'applique aucune règle.

    Pour ajouter un écran : écrire une sous-classe dans un nouveau fichier de ce dossier (`CLE`, et
    `construire` qui pose des panneaux dans `corps`), la déclarer dans `donnees/application.toml`, puis
    ajouter dans les deux fichiers de textes `rail.<cle>` et `ecran.<cle>.titre` et `ecran.<cle>.aide.*`.

    Verrou d'une étape (style parcours), du plus simple au plus fin :
      `EXIGE_RESULTAT` : fermée tant qu'aucun calcul n'a abouti ;
      `EXIGE` (ou `exige = [...]` dans `[[ecran]]`) : fermée tant que chacune de ces étapes n'est pas faite
        (`accompli()` de l'étape nommée) ; une étape ne peut exiger qu'une étape placée avant elle ;
      `accessible()` : condition propre à l'écran, son bandeau étant `MESSAGE_VERROU`.
    `APRES_CALCUL` désigne l'écran que la fenêtre ouvre quand un calcul vient d'aboutir (sinon, le premier écran
    qui exige un résultat).

    Saisie propre (entrées structurées) : un écran qui saisit des entrées déclarées `formulaire = false` dans
    `entrees.toml` les rend par `saisie_structuree()` et les reprend par `definir_structure(valeurs)` ; la fenêtre
    les réunit au formulaire et les valide d'un seul coup (`core.entrees.valider_entrees`). Ce que l'écran garde d'une
    séance à l'autre sans être une entrée passe par `etat()` et `restaurer(etat)` (projet enregistré). Une étape qui a
    sa propre tâche (une analyse) la lance par `lancer()`, que l'essai `-t` joue aussi.
    """

    CLE = ""
    EXIGE_RESULTAT = False  # en style parcours, l'écran reste verrouillé tant qu'aucun calcul n'a abouti
    EXIGE: tuple[str, ...] = ()  # étapes précises à faire avant celle-ci (clés d'écrans placés avant)
    APRES_CALCUL = False  # en style parcours, l'écran que la fenêtre ouvre quand un calcul vient d'aboutir
    MESSAGE_VERROU = "rail.verrouille"  # texte du bandeau quand l'écran est fermé par sa propre condition
    formulaire: Formulaire | None = None

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent)
        self.app = app
        self.panneaux: list[Panneau] = []
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        ttk.Label(self, text=t(f"ecran.{self.CLE}.titre"), style="Titre.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        aide_de_l_ecran(self, f"ecran.{self.CLE}.aide").grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.defilement = ScrollableFrame(self)
        self.defilement.grid(row=2, column=0, sticky="nsew")
        self.corps = self.defilement.interieur
        self.corps.grid_columnconfigure(0, weight=1)
        self.construire(self.corps)

    def construire(self, corps: ttk.Frame) -> None:
        """Pose les panneaux de l'écran (à écrire par chaque écran)."""

    # Verrou fin
    def accessible(self) -> bool:
        """Condition propre à l'écran, en plus des étapes exigées ; vraie par défaut."""
        return True

    def accompli(self) -> bool:
        """Vrai quand l'étape est faite (une étape suivante peut l'exiger) : par défaut, un calcul a abouti."""
        return self.app.resultat is not None

    # Saisie propre et état gardé
    def saisie_structuree(self) -> dict[str, Any]:
        """Entrées saisies par cet écran hors du formulaire (déclarées `formulaire = false`) ; aucune par défaut."""
        return {}

    def definir_structure(self, valeurs: dict[str, Any]) -> None:
        """Reprend les entrées structurées de cet écran (projet ouvert, exemple chargé, langue changée)."""

    def etat(self) -> dict[str, Any]:
        """Ce que l'écran garde dans un projet enregistré, hors des entrées (valeurs JSON) ; rien par défaut."""
        return {}

    def restaurer(self, etat: dict[str, Any]) -> None:
        """Reprend l'état gardé par `etat()` à l'ouverture d'un projet."""

    def lancer(self) -> bool:
        """Lance la tâche propre de l'étape (une analyse) ; rend vrai si une tâche est partie. Aucune par défaut."""
        return False

    # Panneaux
    def ajouter(self, panneau: Panneau, ligne: int | None = None) -> Panneau:
        """Range un panneau dans le corps de l'écran."""
        rang = len(self.panneaux) if ligne is None else ligne
        panneau.grid(row=rang, column=0, sticky="ew", pady=(0 if rang == 0 else 10, 0))
        self.panneaux.append(panneau)
        return panneau

    def rafraichir(self) -> None:
        """Relit l'état de la fenêtre et met les panneaux à jour."""
        for panneau in self.panneaux:
            panneau.mettre_a_jour()

    def basculer(self, occupe: bool) -> None:
        for panneau in self.panneaux:
            panneau.basculer(occupe)
