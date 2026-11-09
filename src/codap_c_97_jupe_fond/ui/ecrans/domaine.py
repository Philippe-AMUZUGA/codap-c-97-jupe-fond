"""
Écrans du domaine : cas unique, classeur, aide.

Chaque écran garde son propre résultat (un calcul d'un écran n'invalide jamais celui d'un autre) dans
`app.resultats_ecrans`, qui survit à la reconstruction de la fenêtre (changement de langue). Les réglages de l'écran
Classeur sont des entrées du schéma déclarées `formulaire = false` : ils sont saisis ici, validés par le
même schéma que le formulaire et gardés dans un projet enregistré. Aucun écran ne calcule : il appelle `core.calculs`
dans un fil par `app.executer`, puis affiche.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Mapping
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ...core import calculs
from ...core.erreurs import ErreurApplication, ErreurSaisie
from ...core.resultat import Resultat
from ...core.schema import Champ, valider
from ...systeme import chemins, diagnostic
from ...textes import formater_nombre, langue, t, t_sortie
from ..panneaux import Panneau, PanneauEntrees, PanneauExport, PanneauResultats, _afficher
from ..widgets import Colonne, Tableau, ZoneFigure, carte
from .base import Ecran

if TYPE_CHECKING:
    from ..app import Application

__all__ = ["Aide", "CasUnique", "Classeur", "ReglagesCompacts"]

LARGEUR_TEXTE = 860
CHAMPS_PAR_RANGEE = 3


def _resultats(app: Application) -> dict[str, Any]:
    """Résultats propres aux écrans, gardés par la fenêtre d'une construction à l'autre."""
    if not hasattr(app, "resultats_ecrans"):
        app.resultats_ecrans = {}  # type: ignore[attr-defined]
    return app.resultats_ecrans  # type: ignore[attr-defined]


def _nombre(valeur: float) -> str:
    return formater_nombre(valeur, 3)


class ReglagesCompacts(ttk.Frame):
    """Réglages d'un écran en grille serrée (trois par rangée) : les entrées du schéma qui commencent par `prefixe`.

    Même schéma et même validation que le formulaire (`core.schema.valider`) ; l'aide de chaque réglage est dans
    l'explication de l'écran, pour laisser la place au résultat.
    """

    def __init__(self, parent: tk.Misc, champs: tuple[Champ, ...], prefixe: str) -> None:
        super().__init__(parent, style="Carte.TFrame")
        self.champs = tuple(c for c in champs if c.nom.startswith(prefixe))
        self._langue = langue()
        self.variables: dict[str, tk.StringVar] = {}
        self.widgets: dict[str, ttk.Widget] = {}
        self._etiquettes: dict[str, dict[str, str]] = {}
        for rang, champ in enumerate(self.champs):
            ligne, colonne = divmod(rang, CHAMPS_PAR_RANGEE)
            base = 3 * colonne
            ttk.Label(self, text=champ.libelle_dans(self._langue), style="Carte.TLabel").grid(
                row=ligne, column=base, sticky="w", padx=(0 if colonne == 0 else 18, 8), pady=4
            )
            variable = tk.StringVar(master=self)
            if champ.type == "choix":
                etiquettes = {champ.etiquette_dans(v, self._langue): v for v in champ.choix}
                self._etiquettes[champ.nom] = etiquettes
                saisie: ttk.Widget = ttk.Combobox(
                    self, textvariable=variable, values=list(etiquettes), state="readonly", width=22
                )
            else:
                saisie = ttk.Entry(self, textvariable=variable, width=10)
            saisie.grid(row=ligne, column=base + 1, sticky="w", pady=4)
            ttk.Label(self, text=champ.unite, style="CarteDoux.TLabel").grid(
                row=ligne, column=base + 2, sticky="w", padx=(4, 0)
            )
            self.variables[champ.nom] = variable
            self.widgets[champ.nom] = saisie
        self.definir({c.nom: c.defaut for c in self.champs})

    def brut(self) -> dict[str, Any]:
        valeurs: dict[str, Any] = {}
        for champ in self.champs:
            saisi = self.variables[champ.nom].get()
            valeurs[champ.nom] = self._etiquettes[champ.nom].get(saisi, saisi) if champ.type == "choix" else saisi
        return valeurs

    def definir(self, valeurs: Mapping[str, Any]) -> None:
        for champ in self.champs:
            if champ.nom not in valeurs or valeurs[champ.nom] is None:
                continue
            valeur = valeurs[champ.nom]
            if champ.type == "choix":
                self.variables[champ.nom].set(champ.etiquette_dans(str(valeur), self._langue))
            elif isinstance(valeur, int | float) and not isinstance(valeur, bool):
                self.variables[champ.nom].set(formater_nombre(float(valeur)))
            else:
                self.variables[champ.nom].set(str(valeur))

    def valider(self) -> dict[str, Any]:
        """Valeurs typées des réglages ; `ErreurSaisie` (motif du premier réglage en défaut) sinon."""
        return valider(self.champs, self.brut())

    def basculer(self, occupe: bool) -> None:
        for champ in self.champs:
            etat = "readonly" if champ.type == "choix" else "normal"
            self.widgets[champ.nom].configure(state="disabled" if occupe else etat)


class PanneauResultatPropre(PanneauResultats):
    """Résultat propre à un écran (lu dans `app.resultats_ecrans`) : figures d'abord, puis mesures et tableaux."""

    def __init__(self, parent: tk.Misc, app: Application, cle: str) -> None:
        super().__init__(parent, app)
        self.cle = cle
        self.vide.configure(text=t(f"{cle}.vide"))

    def afficher(self, resultat: Resultat | None) -> None:
        self.effacer()
        if resultat is None:
            return
        self.vide.grid_remove()
        rang = 0
        for figure in resultat.figures:
            cadre = carte(self.contenu, t("resultats.figure"))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(0 if rang == 0 else 10, 0))
            cadre.grid_columnconfigure(0, weight=1)
            zone = ZoneFigure(cadre, au_enregistrement=self.app.enregistrer_figure)
            zone.grid(row=0, column=0, sticky="ew")
            zone.afficher(figure, naturelle=True)
            self.figures.append(zone)
            rang += 1
        cadre = carte(self.contenu, t("resultats.mesures"))
        cadre.grid(row=rang, column=0, sticky="ew", pady=(0 if rang == 0 else 10, 0))
        cadre.grid_columnconfigure(0, weight=1)
        colonnes: list[Colonne] = [
            ("mesure", t("export.col_mesure"), 320, "w"),
            ("valeur", t("export.col_valeur"), 140, "e"),
        ]
        self.mesures = Tableau(cadre, colonnes, hauteur=len(resultat.mesures))
        self.mesures.grid(row=0, column=0, sticky="ew")
        self.mesures.remplir((t_sortie(m.cle), _afficher(m.valeur)) for m in resultat.mesures)
        for tableau in resultat.tableaux:
            rang += 1
            cadre = carte(self.contenu, t_sortie(tableau.cle))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(10, 0))
            cadre.grid_columnconfigure(0, weight=1)
            vue = Tableau(
                cadre, [(c, t_sortie(c), 110, "e") for c in tableau.colonnes], hauteur=min(10, len(tableau.lignes))
            )
            vue.grid(row=0, column=0, sticky="ew")
            vue.remplir([_afficher(v) for v in ligne] for ligne in tableau.lignes)
            self.tableaux.append(vue)

    def mettre_a_jour(self) -> None:
        resultat = _resultats(self.app).get(self.cle)
        self.afficher(resultat.resultat if isinstance(resultat, calculs.LotClasseur) else resultat)


class PanneauVerdict(Panneau):
    """Verdict du cas unique : enveloppe, puis chaque côté, puis l'avertissement de domaine (pas la couleur seule)."""

    def __init__(self, parent: tk.Misc, app: Application) -> None:
        super().__init__(parent, app)
        self.titre = ttk.Label(self, text="", style="Doux.TLabel", wraplength=520, justify="left")
        self.titre.grid(row=0, column=0, sticky="w")
        self.cotes = ttk.Label(self, text="", style="Doux.TLabel", wraplength=520, justify="left")
        self.cotes.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.domaine = ttk.Label(self, text="", style="Alerte.TLabel", wraplength=520, justify="left")
        self.domaine.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.bind("<Configure>", self._adapter, add="+")

    def _adapter(self, evenement: tk.Event) -> None:
        for etiquette in (self.titre, self.cotes, self.domaine):
            etiquette.configure(wraplength=max(240, evenement.width - 8))

    def mettre_a_jour(self) -> None:
        resultat = self.app.resultat
        if resultat is None:
            self.titre.configure(text=t("cas.sans_verdict"), style="Doux.TLabel")
            self.cotes.configure(text="")
            self.domaine.configure(text="")
            return
        valeur = {m.cle: m.valeur for m in resultat.mesures}
        ok = str(valeur["verdict"]).endswith(": OK")
        self.titre.configure(
            text=t("cas.verdict", verdict=valeur["verdict"], taux=_nombre(valeur["taux"])),
            style="Bon.TLabel" if ok else "Bloquant.TLabel",
        )
        self.cotes.configure(
            text=t(
                "cas.cotes",
                comprime=valeur["verdict_comprime"],
                taux_c=_nombre(valeur["taux_comprime"]),
                tendu=valeur["verdict_tendu"],
                taux_t=_nombre(valeur["taux_tendu"]),
                critere=valeur["critere_determinant"],
            )
        )
        self.domaine.configure(text="" if valeur["applicable"] else t("cas.hors_domaine"))


class CasUnique(Ecran):
    """Les 37 entrées d'une configuration à gauche ; verdict, résultats détaillés et export à droite."""

    CLE = "entrees"

    def construire(self, corps: ttk.Frame) -> None:
        corps.grid_columnconfigure(0, weight=1, uniform="cas")
        corps.grid_columnconfigure(1, weight=1, uniform="cas")
        entrees = PanneauEntrees(corps, self.app, avec_calcul=True)
        entrees.grid(row=0, column=0, sticky="new", padx=(0, 12))
        self.formulaire = entrees.formulaire
        droite = ttk.Frame(corps)
        droite.grid(row=0, column=1, sticky="new")
        droite.grid_columnconfigure(0, weight=1)
        verdict = PanneauVerdict(droite, self.app)
        verdict.grid(row=0, column=0, sticky="ew")
        resultats = PanneauResultats(droite, self.app)
        resultats.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        sortie = PanneauExport(droite, self.app)
        sortie.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.panneaux += [entrees, verdict, resultats, sortie]


class _EcranAReglages(Ecran):
    """Socle de l'écran Classeur : une carte de réglages, des boutons, un résultat propre."""

    PREFIXE = ""

    def poser_reglages(self, panneau: Panneau, rang: int, explication: str) -> ttk.LabelFrame:
        cadre = carte(panneau, t(f"{self.CLE}.carte"))
        cadre.grid(row=rang, column=0, sticky="ew")
        cadre.grid_columnconfigure(0, weight=1)
        self.reglages = ReglagesCompacts(cadre, self.app.schema, self.PREFIXE)
        self.reglages.grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(cadre, text=t(explication), style="CarteDoux.TLabel", wraplength=LARGEUR_TEXTE, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        return cadre

    def valider_reglages(self) -> dict[str, Any] | None:
        try:
            return self.reglages.valider()
        except ErreurSaisie as erreur:
            self.app.erreur(erreur)
            return None

    def saisie_structuree(self) -> dict[str, Any]:
        return self.reglages.brut()

    def definir_structure(self, valeurs: dict[str, Any]) -> None:
        self.reglages.definir(valeurs)

    def accompli(self) -> bool:
        return self.CLE in _resultats(self.app)

    def basculer(self, occupe: bool) -> None:
        super().basculer(occupe)
        self.reglages.basculer(occupe)

    def choisir_dossier(self) -> str:
        return self.app.dialogues.choisir_dossier(t("export.choisir"), self.app.prefs.dossier_export)


class Classeur(_EcranAReglages):
    """Un classeur input_CODAP.xlsx (ou de géométrie EF, converti) calculé par lot, puis sa sortie."""

    CLE = "classeur"
    PREFIXE = "classeur_"

    def construire(self, corps: ttk.Frame) -> None:
        self.chemin = ""
        self.fichier = tk.StringVar(master=self, value="")
        panneau = Panneau(corps, self.app)
        cadre = self.poser_reglages(panneau, 0, "classeur.explication")
        ligne = ttk.Frame(cadre, style="Carte.TFrame")
        ligne.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ligne.grid_columnconfigure(1, weight=1)
        ttk.Label(ligne, text=t("classeur.fichier"), style="Carte.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Entry(ligne, textvariable=self.fichier, state="readonly").grid(row=0, column=1, sticky="ew", padx=(0, 8))
        panneau.bouton(ligne, "classeur.choisir", self.choisir, row=0, column=2)
        rangee = ttk.Frame(panneau)
        rangee.grid(row=1, column=0, sticky="w", pady=(10, 0))
        panneau.bouton(rangee, "classeur.calculer", self.lancer, principal=True, row=0, column=0, padx=(0, 8))
        panneau.bouton(rangee, "classeur.exporter", self.exporter, row=0, column=1)
        self.ajouter(panneau)
        self.ajouter(PanneauResultatPropre(corps, self.app, "classeur"))

    def poser_chemin(self, chemin: str) -> None:
        """Retient le classeur à calculer ; seul son nom est affiché (jamais le chemin du poste)."""
        self.chemin = chemin
        self.fichier.set(Path(chemin).name if chemin else "")

    def choisir(self) -> None:
        choix = self.app.dialogues.ouvrir_fichier(t("classeur.choisir_titre"), self.app.dossier_projets(), "xlsx")
        if choix:
            self.poser_chemin(choix)

    @staticmethod
    def classeur_d_exemple() -> str:
        exemple = chemins.chemin_exemple()
        classeur = exemple.parent / "input_CODAP.xlsx" if exemple is not None else None
        return str(classeur) if classeur is not None and classeur.is_file() else ""

    def lancer(self) -> bool:
        """Calcule le classeur choisi ; sans choix, le classeur d'exemple livré (117 configurations de référence)."""
        if not self.chemin:
            self.poser_chemin(self.classeur_d_exemple())
        if not self.chemin:
            self.app.erreur(t("classeur.absent"))
            return False
        reglages = self.valider_reglages()
        if reglages is None:
            return False
        chemin = self.chemin
        self.app.executer(
            lambda annulation, avancer: calculs.traiter_classeur(
                chemin,
                reglages["classeur_fond"],
                reglages["classeur_situation"],
                reglages["classeur_bras"],
                annulation,
                avancer,
            ),
            nom=t("classeur.nom"),
            au_succes=self._fini,
        )
        return True

    def _fini(self, lot: calculs.LotClasseur) -> None:
        _resultats(self.app)[self.CLE] = lot
        mesures = {m.cle: m.valeur for m in lot.resultat.mesures}
        self.app.info(
            t("classeur.fait", n=mesures["cas"], tenue=mesures["cas_tenue"], hors=mesures["cas_hors_domaine"])
        )
        self.rafraichir()
        self.defilement.montrer(self.panneaux[-1])  # le résultat vient en haut de la zone visible

    def exporter(self) -> None:
        lot = _resultats(self.app).get(self.CLE)
        if lot is None:
            self.app.banniere.afficher(t("classeur.pas_de_resultat"), "alerte")
            return
        dossier = self.choisir_dossier()
        if not dossier:
            return
        try:
            ecrits = calculs.exporter_classeur(lot, dossier)
        except ErreurApplication as erreur:
            self.app.erreur(erreur)
            return
        self.app.info(t("export.fait", n=len(ecrits), dossier=diagnostic.anonymiser(dossier)))

    def etat(self) -> dict[str, Any]:
        return {"fichier": self.chemin} if self.chemin else {}

    def restaurer(self, etat: dict[str, Any]) -> None:
        if isinstance(etat.get("fichier"), str):
            self.poser_chemin(etat["fichier"])


class Aide(Ecran):
    """Périmètre, conventions mécaniques, validation, références et licence."""

    CLE = "aide"
    RUBRIQUES = ("perimetre", "conventions", "validation", "references", "apropos")

    def construire(self, corps: ttk.Frame) -> None:
        panneau = Panneau(corps, self.app)
        for rang, rubrique in enumerate(self.RUBRIQUES):
            cadre = carte(panneau, t(f"aide_ecran.{rubrique}.titre"))
            cadre.grid(row=rang, column=0, sticky="ew", pady=(0 if rang == 0 else 10, 0))
            cadre.grid_columnconfigure(0, weight=1)
            texte = ttk.Label(
                cadre,
                text=t(f"aide_ecran.{rubrique}.texte"),
                style="Carte.TLabel",
                wraplength=LARGEUR_TEXTE,
                justify="left",
            )
            texte.grid(row=0, column=0, sticky="w")
            cadre.bind("<Configure>", lambda e, w=texte: w.configure(wraplength=max(240, e.width - 40)), add="+")
        self.ajouter(panneau)

    def accompli(self) -> bool:
        return True
