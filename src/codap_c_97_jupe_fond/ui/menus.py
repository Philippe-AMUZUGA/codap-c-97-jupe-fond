"""
Barre de menus et raccourcis clavier, communs à tous les styles d'interface.

Fichier (ouvrir, enregistrer, récents, exporter, quitter), Affichage (taille, thème, langue, journal) et Aide
(guide, journal, diagnostic, à propos, nouvelle version). Les raccourcis sont déclarés dans `application.toml`
(`[raccourci]`) ; `lier_raccourcis` les pose tous et rend ce qui a été lié, pour que les tests vérifient que chaque
raccourci déclaré a une action.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from ..textes import LANGUES, t

if TYPE_CHECKING:
    from .app import Application

__all__ = ["Menus", "construire_menus", "decrire_raccourci", "lier_raccourcis"]

_TOUCHES = {
    "plus": (["plus", "equal", "KP_Add"], "+"),
    "minus": (["minus", "KP_Subtract"], "-"),
    "Escape": (["Escape"], "Esc"),
    "Left": (["Left"], "←"),
    "Right": (["Right"], "→"),
}


def decrire_raccourci(declaration: str, plateforme: str | None = None) -> tuple[list[str], str]:
    """Raccourci déclaré (`Mod+o`, `F5`, `Alt+Left`) : séquences Tk à lier et libellé pour les menus.

    `Mod` est Ctrl sur Windows et Linux, Commande sur macOS ; une lettre est liée en minuscule et en majuscule
    (verrouillage des majuscules).
    """
    plateforme = plateforme or sys.platform
    *modificateurs, touche = declaration.split("+")
    tk_mod, libelle_mod = [], []
    for nom in modificateurs:
        if nom == "Mod":
            nom = "Command" if plateforme == "darwin" else "Control"
        tk_mod.append(nom)
        libelle_mod.append({"Control": "Ctrl", "Command": "Cmd"}.get(nom, nom))
    touches, libelle_touche = _TOUCHES.get(touche, ([touche], touche.upper() if len(touche) == 1 else touche))
    if len(touche) == 1 and touche.isalpha():
        touches = [touche.lower(), touche.upper()]
    elif touche.isdigit():
        touches = [f"Key-{touche}"]  # `<Control-3>` serait lu comme Control et bouton 3 de la souris
    sequences = ["<" + "-".join([*tk_mod, k]) + ">" for k in touches]
    return sequences, "+".join([*libelle_mod, libelle_touche])


def _gestionnaire(action: Callable[[], object]) -> Callable[[tk.Event], str]:
    """Rappel d'un raccourci : lance l'action, puis arrête la propagation de l'événement."""

    def rappel(_evenement: tk.Event) -> str:
        action()
        return "break"

    return rappel


def lier_raccourcis(
    app: Application, declarations: Mapping[str, str], actions: Mapping[str, Callable[[], object]]
) -> dict[str, list[str]]:
    """Lie chaque raccourci déclaré à son action ; rend, par nom d'action, les séquences liées.

    Une déclaration sans action est une erreur de configuration (`KeyError`) : mieux vaut l'apprendre à l'ouverture
    qu'au premier appui.
    """
    liees: dict[str, list[str]] = {}
    for nom, declaration in declarations.items():
        action = actions[nom]
        sequences, _ = decrire_raccourci(declaration)
        for sequence in sequences:
            app.bind_all(sequence, _gestionnaire(action))
        liees[nom] = sequences
    for numero in range(1, 10):  # Ctrl+1 à Ctrl+9 : écran du rail correspondant
        if numero <= app.corps.nombre_ecrans:
            sequences, _ = decrire_raccourci(f"Mod+{numero}")
            for sequence in sequences:
                app.bind_all(sequence, _gestionnaire(lambda n=numero - 1: app.corps.afficher(n)))
            liees[f"ecran_{numero}"] = sequences
    return liees


class Menus:
    """Barre de menus d'une fenêtre, avec les variables Tk qui suivent le thème, la langue et le journal."""

    def __init__(self, app: Application) -> None:
        self.app = app
        self.barre = tk.Menu(app, tearoff=False)
        self.theme = tk.StringVar(master=app, value=app.prefs.theme)
        self.langue = tk.StringVar(master=app, value=app.langue)
        self.journal = tk.BooleanVar(master=app, value=app.prefs.journal_visible)
        self._construire()

    def _libelle(self, cle: str, action: str | None = None) -> dict[str, str]:
        """Options d'une entrée de menu : texte, et raccourci affiché s'il est déclaré."""
        options = {"label": t(cle)}
        declaration = self.app.raccourcis.get(action) if action else None
        if declaration:
            options["accelerator"] = decrire_raccourci(declaration)[1]
        return options

    def _construire(self) -> None:
        a = self.app
        fichier = tk.Menu(self.barre, tearoff=False)
        fichier.add_command(command=a.ouvrir, **self._libelle("menu.ouvrir", "ouvrir"))
        fichier.add_command(command=a.enregistrer, **self._libelle("menu.enregistrer", "enregistrer"))
        self.recents = tk.Menu(fichier, tearoff=False, postcommand=self._remplir_recents)
        fichier.add_cascade(label=t("menu.recents"), menu=self.recents)
        fichier.add_separator()
        fichier.add_command(command=a.exporter, **self._libelle("menu.exporter", "exporter"))
        fichier.add_separator()
        fichier.add_command(command=a.quitter, **self._libelle("menu.quitter", "quitter"))
        self.barre.add_cascade(label=t("menu.fichier"), menu=fichier)

        affichage = tk.Menu(self.barre, tearoff=False)
        affichage.add_command(command=a.police_plus, **self._libelle("menu.police_plus", "police_plus"))
        affichage.add_command(command=a.police_moins, **self._libelle("menu.police_moins", "police_moins"))
        affichage.add_command(command=a.police_normale, **self._libelle("menu.police_normale", "police_normale"))
        affichage.add_separator()
        for theme in ("clair", "sombre"):
            affichage.add_radiobutton(
                label=t(f"menu.theme_{theme}"),
                variable=self.theme,
                value=theme,
                command=lambda th=theme: a.definir_theme(th),
            )
        if len(LANGUES) > 1:
            affichage.add_separator()
            for code in LANGUES:
                affichage.add_radiobutton(
                    label=t(f"menu.langue_{code}"),
                    variable=self.langue,
                    value=code,
                    command=lambda c=code: a.definir_langue(c),
                )
        affichage.add_separator()
        affichage.add_checkbutton(
            variable=self.journal,
            command=lambda: a.afficher_journal(self.journal.get()),
            **self._libelle("menu.journal", "journal"),
        )
        self.barre.add_cascade(label=t("menu.affichage"), menu=affichage)

        aide = tk.Menu(self.barre, tearoff=False)
        aide.add_command(command=a.afficher_guide, **self._libelle("menu.guide", "aide"))
        aide.add_command(label=t("menu.diagnostic"), command=a.copier_diagnostic)
        aide.add_command(label=t("menu.dossier_journaux"), command=a.ouvrir_dossier_journaux)
        aide.add_separator()
        aide.add_command(label=t("menu.page_projet"), command=a.page_projet)
        aide.add_command(label=t("menu.nouvelle_version"), command=a.nouvelle_version)
        aide.add_command(label=t("menu.apropos"), command=a.a_propos)
        self.barre.add_cascade(label=t("menu.aide"), menu=aide)

    def _remplir_recents(self) -> None:
        """Remplit le sous-menu des fichiers récents à chaque ouverture du menu."""
        self.recents.delete(0, "end")
        recents = [r for r in self.app.prefs.recents if Path(r).is_file()]
        for chemin in recents:
            self.recents.add_command(label=Path(chemin).name, command=lambda c=chemin: self.app.ouvrir(c))
        if recents:
            self.recents.add_separator()
            self.recents.add_command(label=t("menu.recents_effacer"), command=self.app.effacer_recents)
        else:
            self.recents.add_command(label=t("menu.recents_aucun"), state="disabled")


def construire_menus(app: Application) -> Menus:
    """Crée la barre de menus et l'installe sur la fenêtre."""
    menus = Menus(app)
    app.configure(menu=menus.barre)
    return menus
