"""
Disposition à rail : une colonne d'étapes à gauche, l'écran de l'étape au centre.

Deux familles, choisies par `style` dans `application.toml` :
  `parcours` : les écrans se suivent ; une étape s'ouvre quand ce qu'elle exige est fait (un calcul abouti, ou des
               étapes précises : `EXIGE` de l'écran, ou `exige = [...]` dans sa déclaration) ;
  `onglets`  : tous les écrans sont ouverts dès le départ, dans l'ordre que l'utilisateur veut.
Les écrans sont déclarés dans `application.toml` (`[[ecran]]`) et vivent dans le dossier `ecrans/`. Ce fichier est
choisi quand le style n'est pas `un` ; `ecran_unique.py` est son pendant pour une seule page. Les deux exposent la
même classe `Corps` à `app.py`.
"""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ..textes import t
from .ecrans.base import Ecran
from .formulaire import Formulaire
from .panneaux import PanneauExport

if TYPE_CHECKING:
    from .app import Application

__all__ = ["Corps", "etapes_exigees"]

LARGEUR_RAIL = 22


def etapes_exigees(declarations: list[dict[str, Any]], classes: list[type[Ecran]]) -> list[tuple[int, ...]]:
    """Rangs des étapes que chaque écran exige : `exige` de sa déclaration, sinon `EXIGE` de sa classe.

    Une clé inconnue, l'écran lui-même ou une étape placée après lui est refusé (`ValueError`) : un parcours dont
    une étape attend une étape suivante ne s'ouvrirait jamais.
    """
    rangs = {str(d["cle"]): k for k, d in enumerate(declarations)}
    exigences: list[tuple[int, ...]] = []
    for k, (declaration, classe) in enumerate(zip(declarations, classes, strict=True)):
        cles = declaration.get("exige", classe.EXIGE)
        if isinstance(cles, str):
            cles = [cles]
        exigees = []
        for cle in cles:
            if cle not in rangs:
                raise ValueError(f"Écran {declaration['cle']} : étape exigée inconnue {cle!r}.")
            if rangs[cle] >= k:
                raise ValueError(f"Écran {declaration['cle']} : l'étape exigée {cle!r} n'est pas placée avant lui.")
            exigees.append(rangs[cle])
        exigences.append(tuple(exigees))
    return exigences


class Corps(ttk.Frame):
    """Corps de la fenêtre : rail d'étapes et écrans empilés."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent)
        self.app = app
        self.parcours = app.style == "parcours"
        self.courant = 0
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.ecrans: list[Ecran] = []
        self._rail: list[ttk.Button] = []
        rail = ttk.Frame(self)
        rail.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        zone = ttk.Frame(self)
        zone.grid(row=0, column=1, sticky="nsew")
        zone.grid_rowconfigure(0, weight=1)
        zone.grid_columnconfigure(0, weight=1)
        classes = [_charger_classe(d["module"], d["classe"]) for d in app.declarations_ecrans]
        self.exigences = etapes_exigees(app.declarations_ecrans, classes)
        for numero, classe in enumerate(classes):
            ecran = classe(zone, app)
            ecran.grid(row=0, column=0, sticky="nsew")
            self.ecrans.append(ecran)
            bouton = ttk.Button(
                rail,
                text=f"{numero + 1}. {t('rail.' + ecran.CLE)}",
                style="Rail.TButton",
                width=LARGEUR_RAIL,
                command=lambda n=numero: self.afficher(n),
            )
            bouton.grid(row=numero, column=0, sticky="ew", pady=2)
            self._rail.append(bouton)
        self.afficher(0)

    @property
    def nombre_ecrans(self) -> int:
        return len(self.ecrans)

    @property
    def formulaire(self) -> Formulaire:
        for ecran in self.ecrans:
            if ecran.formulaire is not None:
                return ecran.formulaire
        raise LookupError("Aucun écran ne porte le formulaire des entrées.")

    def parametres_export(self) -> dict[str, Any]:
        """Dossier, nom de base et formats choisis dans le panneau d'export (valeurs par défaut sinon)."""
        for ecran in self.ecrans:
            for panneau in ecran.panneaux:
                if isinstance(panneau, PanneauExport):
                    return panneau.parametres()
        return {}

    # Entrées structurées et état gardé, réunis écran par écran
    def saisie_structuree(self) -> dict[str, Any]:
        """Entrées saisies hors du formulaire par les écrans (une liste de facteurs, par exemple)."""
        saisie: dict[str, Any] = {}
        for ecran in self.ecrans:
            saisie.update(ecran.saisie_structuree())
        return saisie

    def definir_structure(self, valeurs: dict[str, Any]) -> None:
        for ecran in self.ecrans:
            ecran.definir_structure(valeurs)

    def etat(self) -> dict[str, Any]:
        """État gardé par chaque écran, rangé sous sa clé (projet enregistré)."""
        return {e.CLE: contenu for e in self.ecrans if (contenu := e.etat())}

    def restaurer(self, etat: dict[str, Any]) -> None:
        for ecran in self.ecrans:
            contenu = etat.get(ecran.CLE)
            if isinstance(contenu, dict):
                ecran.restaurer(contenu)

    # Navigation
    def motif_verrou(self, numero: int) -> str | None:
        """Pourquoi l'écran est fermé (texte du bandeau), ou None s'il peut s'ouvrir."""
        if not 0 <= numero < len(self.ecrans):
            return t("rail.verrouille")
        ecran = self.ecrans[numero]
        if not self.parcours:
            return None
        if ecran.EXIGE_RESULTAT and self.app.resultat is None:
            return t("rail.verrouille")
        for rang in self.exigences[numero]:
            if not self.ecrans[rang].accompli():
                return t("rail.verrouille_etape", etape=self.libelle_ecran(rang))
        return None if ecran.accessible() else t(ecran.MESSAGE_VERROU)

    def accessible(self, numero: int) -> bool:
        """Vrai si l'écran peut s'ouvrir : toujours en onglets ; en parcours, selon ce qu'il exige."""
        return 0 <= numero < len(self.ecrans) and self.motif_verrou(numero) is None

    def afficher(self, numero: int) -> None:
        """Ouvre l'écran ; un écran verrouillé reste fermé et le bandeau dit pourquoi."""
        if not 0 <= numero < len(self.ecrans):
            return
        motif = self.motif_verrou(numero)
        if motif is not None:
            self.app.banniere.afficher(motif, "alerte")
            return
        self.courant = numero
        ecran = self.ecrans[numero]
        ecran.tkraise()
        ecran.rafraichir()
        self.mettre_a_jour_rail()

    def precedent(self) -> None:
        self.afficher(self.courant - 1)

    def suivant(self) -> None:
        self.afficher(self.courant + 1)

    def libelle_ecran(self, numero: int) -> str:
        return t("rail." + self.ecrans[numero].CLE) if 0 <= numero < len(self.ecrans) else ""

    def mettre_a_jour_rail(self) -> None:
        for numero, bouton in enumerate(self._rail):
            bouton.configure(
                style="RailActif.TButton" if numero == self.courant else "Rail.TButton",
                state="normal" if self.accessible(numero) else "disabled",
            )

    # Interface commune avec ecran_unique.Corps
    def afficher_resultat(self) -> None:
        """Appelé par la fenêtre quand un calcul vient d'aboutir : en parcours, on passe à l'écran qui le montre."""
        self.mettre_a_jour_rail()
        cible = next((k for k, e in enumerate(self.ecrans) if e.APRES_CALCUL), None)
        if cible is None:
            cible = next((k for k, e in enumerate(self.ecrans) if e.EXIGE_RESULTAT), None)
        if cible is not None and self.parcours:
            self.afficher(cible)
        else:
            self.mettre_a_jour()

    def effacer_resultat(self) -> None:
        """Le résultat est effacé (retour en arrière) : un écran qui n'est plus accessible rend la main au premier."""
        if not self.accessible(self.courant):
            self.courant = 0
            self.ecrans[0].tkraise()
        self.mettre_a_jour()

    def mettre_a_jour(self) -> None:
        for ecran in self.ecrans:
            ecran.rafraichir()
        self.mettre_a_jour_rail()

    def basculer(self, occupe: bool) -> None:
        for ecran in self.ecrans:
            ecran.basculer(occupe)


def _charger_classe(module: str, classe: str) -> type[Ecran]:
    """Classe d'écran déclarée dans application.toml (fichier de `ui/ecrans/`)."""
    fichier = importlib.import_module(f".ecrans.{module}", package=__package__)
    return getattr(fichier, classe)
