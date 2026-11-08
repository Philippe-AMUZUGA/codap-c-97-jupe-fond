"""
Fenêtre principale.

La fenêtre porte la barre de menus, le titre, un bandeau de messages, le corps (un seul écran ou un rail
d'étapes, selon le style de `application.toml`), le journal visible (replié sur sa dernière ligne par défaut, pour
laisser sa hauteur à la zone centrale) et un pied de page (état, progression, annulation, crédit). Elle n'applique
aucune règle : elle envoie des actions au noyau, dans un fil (`worker.Pilote`), et affiche ce qu'il rend. La boucle
Tk n'attend jamais. Les entrées complètes sont celles du formulaire et celles que des écrans saisissent à part
(entrées structurées), validées d'un seul coup ; un projet enregistré garde les entrées et l'état des écrans.
"""

from __future__ import annotations

import contextlib
import ctypes
import importlib
import logging
import sys
import tkinter as tk
import tomllib
import webbrowser
from collections import deque
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import Any

from .. import ANNEE, AUTEUR, LICENCE, NOM, SLUG, URL_DEPOT, URL_RELEASES, __version__
from ..core import calculs, export, fichiers
from ..core.entrees import valider_entrees
from ..core.erreurs import ErreurApplication, ErreurSaisie
from ..core.resultat import Resultat
from ..core.schema import Champ, charger_schema
from ..core.taches import Fonction
from ..systeme import chemins, diagnostic, journal, preferences
from ..textes import LANGUES, definir_langue, langue, t
from . import theme
from .dialogues import Dialogues
from .menus import Menus, construire_menus, lier_raccourcis
from .widgets import Banniere, ZoneJournal, carte
from .worker import Pilote, message_d_erreur

__all__ = ["Application", "charger_declaration", "lancer", "preparer_processus"]

journal_app = logging.getLogger(__name__)
INTERVALLE_JOURNAL_MS = 200


def charger_declaration() -> dict[str, Any]:
    """Contenu de `donnees/application.toml` : style, écrans, fenêtre, raccourcis."""
    source = Path(__file__).resolve().parents[1] / "donnees" / "application.toml"
    return tomllib.loads(source.read_text(encoding="utf-8"))


def preparer_processus() -> None:
    """Réglages du processus à faire avant de créer la fenêtre : DPI et identité de la barre des tâches (Windows)."""
    if sys.platform != "win32":
        return
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{SLUG}.{__version__}")


def _module_corps(style: str) -> Any:
    """Fichier de disposition du style : `ecran_unique` pour un écran, `rail` pour parcours et onglets."""
    return importlib.import_module(".ecran_unique" if style == "un" else ".rail", package=__package__)


class Application(tk.Tk):
    """Fenêtre de l'application."""

    def __init__(self, *, dialogues: Dialogues | None = None, flux: journal.FluxInterface | None = None) -> None:
        super().__init__()
        self.declaration = charger_declaration()
        self.style = str(self.declaration["application"]["style"])
        self.declarations_ecrans: list[dict[str, str]] = list(self.declaration.get("ecran", []))
        self.raccourcis: dict[str, str] = dict(self.declaration.get("raccourci", {}))
        self.prefs = preferences.charger()
        self.langue = definir_langue(self.prefs.langue if self.prefs.langue in LANGUES else langue())
        self.schema: tuple[Champ, ...] = charger_schema()
        self.dialogues = dialogues or Dialogues()
        self.flux = flux or journal.installer()
        self.resultat: Resultat | None = None
        self.entrees: dict[str, Any] | None = None
        self.derniers_fichiers: list[Path] = []
        self.erreurs_de_rappel: list[BaseException] = []
        self._lignes_journal: deque[str] = deque(maxlen=ZoneJournal.LIGNES_MAX)
        self.statut = tk.StringVar(value="")
        self.progression = tk.DoubleVar(value=0.0)
        self.pilote = Pilote(self, self._montrer_progression, self._basculer)
        self._horloge: str | None = None
        self._ferme = False
        self.report_callback_exception = self._exception_de_rappel  # type: ignore[assignment]
        self.resizable(True, True)
        self._geometrie()
        theme.appliquer(self, self.prefs.theme, self.prefs.taille_police)
        self._icone()
        self._construire()
        self.protocol("WM_DELETE_WINDOW", self.quitter)
        self._horloge = self.after(INTERVALLE_JOURNAL_MS, self._sonder_journal)
        journal_app.info("%s %s démarre (style %s, langue %s)", NOM, __version__, self.style, self.langue)

    # ====================================================================
    # Construction
    # ====================================================================
    def _geometrie(self) -> None:
        fenetre = self.declaration.get("fenetre", {})
        largeur = min(int(fenetre.get("largeur", 1180)), self.winfo_screenwidth() - 20)
        hauteur = min(int(fenetre.get("hauteur", 760)), self.winfo_screenheight() - 110)
        x = max(0, (self.winfo_screenwidth() - largeur) // 2)
        y = max(0, (self.winfo_screenheight() - hauteur) // 3)
        self.geometry(f"{largeur}x{hauteur}+{x}+{y}")
        self.minsize(
            min(int(fenetre.get("largeur_min", 960)), largeur), min(int(fenetre.get("hauteur_min", 560)), hauteur)
        )

    def _icone(self) -> None:
        with contextlib.suppress(tk.TclError):
            ico = chemins.chemin_asset("icone.ico")
            if ico is not None and sys.platform == "win32":
                self.iconbitmap(str(ico))
                return
            png = chemins.chemin_asset("icone.png")
            if png is not None:
                self._image_icone = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._image_icone)

    def _construire(self) -> None:
        """Construit (ou reconstruit, après un changement de langue) menus, corps, journal et pied de page."""
        for enfant in self.winfo_children():
            enfant.destroy()
        self.title(t("app.titre"))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.menus: Menus = construire_menus(self)
        externe = ttk.Frame(self, padding=(16, 14, 16, 8))
        externe.grid(row=0, column=0, sticky="nsew")
        externe.grid_rowconfigure(2, weight=1)
        externe.grid_columnconfigure(0, weight=1)
        ttk.Label(externe, text=t("app.nom"), style="Titre.TLabel").grid(row=0, column=0, sticky="w")
        self.banniere = Banniere(externe)
        self.banniere.grid(row=1, column=0, sticky="ew", pady=(6, 6))
        self.banniere.masquer()  # posée par grid(), elle apparaît tant qu'on ne la cache pas
        self.corps = _module_corps(self.style).Corps(externe, self)
        self.corps.grid(row=2, column=0, sticky="nsew")
        self.cadre_journal = carte(externe, t("journal.titre"), padding=(8, 4))
        self.cadre_journal.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.cadre_journal.grid_columnconfigure(0, weight=1)
        self.zone_journal = ZoneJournal(self.cadre_journal, hauteur=5)
        self.zone_journal.grid(row=0, column=0, sticky="ew")
        self.zone_journal.ajouter(self._lignes_journal)
        self.bouton_journal = ttk.Button(self.cadre_journal, style="Petit.TButton", command=self.basculer_repli_journal)
        self.bouton_journal.grid(row=0, column=1, sticky="ne", padx=(8, 0))
        self._pied(externe).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.afficher_journal(self.prefs.journal_visible)
        self.replier_journal(self.prefs.journal_replie)
        self.statut.set(t("pied.pret"))
        self.actions = self._actions()
        self.liaisons = lier_raccourcis(self, self.raccourcis, self.actions)

    def _pied(self, parent: tk.Misc) -> ttk.Frame:
        pied = ttk.Frame(parent)
        pied.grid_columnconfigure(0, weight=1)
        ttk.Separator(pied).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        ttk.Label(pied, textvariable=self.statut).grid(row=1, column=0, sticky="w")
        self.barre = ttk.Progressbar(pied, variable=self.progression, maximum=100, length=220)
        self.barre.grid(row=1, column=1, padx=10)
        self.bouton_annuler = ttk.Button(pied, text=t("pied.annuler"), command=self.annuler, state="disabled")
        self.bouton_annuler.grid(row=1, column=2)
        credit = t("pied.credit", nom=NOM, version=__version__, licence=LICENCE)
        ttk.Label(pied, text=credit, style="Doux.TLabel").grid(row=1, column=3, padx=(14, 0))
        return pied

    def _actions(self) -> dict[str, Callable[[], object]]:
        """Action liée à chaque raccourci déclaré dans `application.toml`."""
        return {
            "ouvrir": self.ouvrir,
            "enregistrer": self.enregistrer,
            "exporter": self.exporter,
            "quitter": self.quitter,
            "aide": self.afficher_guide,
            "calculer": self.calculer,
            "annuler": self.annuler,
            "police_plus": self.police_plus,
            "police_moins": self.police_moins,
            "police_normale": self.police_normale,
            "journal": self.basculer_journal,
            "etape_precedente": lambda: self.corps.precedent(),
            "etape_suivante": lambda: self.corps.suivant(),
        }

    # ====================================================================
    # Messages, état, journal
    # ====================================================================
    @property
    def occupe(self) -> bool:
        return self.pilote.occupe

    def _montrer_progression(self, fraction: float, message: str) -> None:
        self.progression.set(100.0 * fraction)
        if message:
            self.statut.set(message)
        elif not self.pilote.occupe:
            self.statut.set(t("pied.pret"))

    def _basculer(self, occupe: bool) -> None:
        self.configure(cursor="watch" if occupe else "")
        self.bouton_annuler.configure(state="normal" if occupe else "disabled")
        self.corps.basculer(occupe)

    def erreur(self, erreur: BaseException | str, *, etape: str | None = None) -> None:
        """Affiche le motif d'un refus tel quel (bandeau, état, journal) ; une erreur imprévue, en termes sobres."""
        texte = erreur if isinstance(erreur, str) else message_d_erreur(erreur, etape)
        journal_app.warning("%s", texte)
        self.banniere.afficher(texte, "bloquant")
        self.statut.set(texte[:140])

    def info(self, texte: str) -> None:
        journal_app.info("%s", texte)
        self.banniere.afficher(texte, "bon")

    def confirmer(self, texte: str) -> bool:
        return bool(self.dialogues.confirmer(texte))

    def _sonder_journal(self) -> None:
        """Verse au journal visible les lignes arrivées, et montre les incidents (exceptions non attrapées)."""
        if self._ferme:
            return
        self._verser_journal()
        while not journal.incidents.empty():
            self.banniere.afficher(t("erreur.incident", detail=journal.incidents.get_nowait()), "bloquant")
        self._horloge = self.after(INTERVALLE_JOURNAL_MS, self._sonder_journal)

    def _verser_journal(self) -> None:
        """Passe les lignes arrivées au journal visible et à l'historique (gardé quand la fenêtre est reconstruite)."""
        lignes = self.flux.vider()
        self._lignes_journal.extend(lignes)
        self.zone_journal.ajouter(lignes)

    def _exception_de_rappel(self, genre: type[BaseException], valeur: BaseException, trace: Any) -> None:
        """Exception levée dans un rappel de Tk : journal, bandeau, mémoire pour l'essai automatique."""
        self.erreurs_de_rappel.append(valeur)
        journal_app.critical("exception dans un rappel de l'interface", exc_info=(genre, valeur, trace))
        with contextlib.suppress(tk.TclError, AttributeError):
            self.banniere.afficher(t("erreur.incident", detail=f"{genre.__name__} : {valeur}"), "bloquant")

    def afficher_journal(self, visible: bool) -> None:
        """Montre ou cache la zone du journal (réglage gardé)."""
        self.prefs.journal_visible = bool(visible)
        if visible:
            self.cadre_journal.grid()
        else:
            self.cadre_journal.grid_remove()
        self.menus.journal.set(bool(visible))

    def basculer_journal(self) -> None:
        self.afficher_journal(not self.prefs.journal_visible)

    def replier_journal(self, replie: bool) -> None:
        """Replié : le journal ne montre que sa dernière ligne et la zone centrale garde la hauteur (réglage gardé)."""
        self.prefs.journal_replie = bool(replie)
        self.zone_journal.replier(replie)
        self.bouton_journal.configure(text=t("journal.deplier" if replie else "journal.replier"))

    def basculer_repli_journal(self) -> None:
        self.replier_journal(not self.prefs.journal_replie)

    # ====================================================================
    # Calcul
    # ====================================================================
    def executer(
        self,
        fonction: Fonction[Any],
        *,
        nom: str,
        au_succes: Callable[[Any], None],
        en_echec: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Lance un calcul dans un fil ; le résultat revient dans Tk, l'erreur s'affiche dans le bandeau."""
        if self.occupe:
            return
        self.banniere.masquer()
        self.pilote.lancer(
            fonction,
            nom=nom,
            au_succes=au_succes,
            en_echec=en_echec or (lambda erreur: self.erreur(erreur, etape=nom)),
            si_annulee=lambda: self.statut.set(t("pied.annule")),
        )

    def annuler(self) -> None:
        """Demande l'arrêt du calcul en cours ; sinon ferme le bandeau de message."""
        if self.occupe:
            journal_app.info("annulation demandée")
            self.pilote.annuler()
        else:
            self.banniere.masquer()

    def saisie_complete(self) -> dict[str, Any]:
        """Entrées complètes et validées : formulaire (qui marque ses champs en défaut), puis entrées des écrans."""
        options = self.corps.formulaire.valider()
        return valider_entrees({**options, **self.corps.saisie_structuree()}, self.schema)

    def calculer(self) -> None:
        """Valide les entrées complètes puis calcule dans un fil."""
        if self.occupe:
            return
        try:
            entrees = self.saisie_complete()
        except ErreurSaisie as erreur:
            self.erreur(erreur)
            return
        self.entrees = entrees
        self.executer(
            lambda annulation, avancer: calculs.calculer(entrees, annulation, avancer),
            nom=t("calcul.nom"),
            au_succes=self._calcul_fini,
        )

    def _calcul_fini(self, resultat: Resultat) -> None:
        self.resultat = resultat
        self.derniers_fichiers = []
        self.info(t("calcul.fait"))
        self.corps.afficher_resultat()

    # ====================================================================
    # Fichiers d'entrées
    # ====================================================================
    def valeurs_par_defaut(self) -> None:
        """Remet les valeurs par défaut du schéma dans le formulaire et dans les écrans qui saisissent à part."""
        self.definir_entrees({c.nom: c.defaut for c in self.schema if c.defaut is not None})
        self.banniere.masquer()

    def definir_entrees(self, valeurs: dict[str, Any]) -> None:
        """Remet des entrées dans la fenêtre : le formulaire, puis les écrans qui saisissent des entrées structurées."""
        self.corps.formulaire.definir(valeurs)
        self.corps.definir_structure(valeurs)

    def charger_exemple(self) -> None:
        """Remplit le formulaire avec les valeurs de l'exemple livré (`examples/exemple.json`)."""
        chemin = chemins.chemin_exemple()
        if chemin is None:
            self.erreur(t("fichier.exemple_absent"))
            return
        self.ouvrir(chemin, memoriser=False)

    def dossier_projets(self) -> str:
        """Dossier proposé pour ouvrir ou enregistrer un projet : le dernier dossier d'export, sinon les données."""
        return self.prefs.dossier_export or str(chemins.dossier_donnees())

    def ouvrir(self, chemin: str | Path | None = None, *, memoriser: bool = True) -> None:
        """Charge un projet enregistré, un fichier d'entrées ou le projet.json d'un export ; refuse un fichier invalide.

        Les entrées vont au formulaire et aux écrans qui les saisissent, l'état gardé aux écrans ; si le projet
        avait un calcul abouti, le calcul est relancé sur les mêmes entrées.
        """
        if chemin is None:
            chemin = self.dialogues.ouvrir_fichier(t("menu.ouvrir_titre"), self.dossier_projets())
        if not chemin:
            return
        try:
            brut, etat = fichiers.lire_projet(chemin)
            valeurs = valider_entrees(brut, self.schema)  # un fichier invalide est refusé en entier, rien n'est chargé
        except ErreurSaisie as erreur:
            self.erreur(str(erreur) if not erreur.par_champ else f"{Path(chemin).name} : {erreur}")
            return
        self.definir_entrees(valeurs)
        ecrans = etat.get("ecrans", {})
        self.corps.restaurer(ecrans if isinstance(ecrans, dict) else {})
        if memoriser:
            preferences.ajouter_recent(self.prefs, chemin)
        self.info(t("fichier.ouvert", nom=Path(chemin).name))
        if etat.get("calcule") is True:
            self.calculer()

    def enregistrer(self, chemin: str | Path | None = None) -> None:
        """Enregistre le projet : entrées complètes valides et état des écrans, dans un fichier JSON."""
        try:
            valeurs = self.saisie_complete()
        except ErreurSaisie as erreur:
            self.erreur(erreur)
            return
        if chemin is None:
            nom = f"{self.nom_de_base(valeurs)}.json"
            chemin = self.dialogues.enregistrer_fichier(t("menu.enregistrer_titre"), nom, self.dossier_projets())
        if not chemin:
            return
        etat = {"calcule": self.resultat is not None and self.entrees == valeurs, "ecrans": self.corps.etat()}
        try:
            cible = fichiers.ecrire_projet(chemin, valeurs, etat)
        except OSError as erreur:
            journal_app.error("écriture impossible : %s", erreur)
            self.erreur(t("fichier.ecriture_impossible", nom=Path(chemin).name))
            return
        preferences.ajouter_recent(self.prefs, cible)
        self.info(t("fichier.enregistre", nom=cible.name))

    def effacer_recents(self) -> None:
        self.prefs.recents = []

    # ====================================================================
    # Export
    # ====================================================================
    def nom_de_base(self, entrees: dict[str, Any] | None = None) -> str:
        """Nom de base des fichiers : premier champ texte des entrées (dernières calculées), sinon `resultats`."""
        premier = next((c for c in self.schema if c.type == "texte"), None)
        source = entrees if entrees is not None else (self.entrees or {})
        return str(source.get(premier.nom, "") if premier else "") or "resultats"

    def enregistrer_figure(self, figure: Any, chemin: str | Path | None = None) -> Path | None:
        """Enregistre une figure en image, PNG ou SVG selon l'extension choisie ; rend le chemin écrit (None sinon)."""
        if chemin is None:
            nom = f"{self.nom_de_base()}_figure.png"
            chemin = self.dialogues.enregistrer_fichier(t("image.titre"), nom, self.dossier_projets(), genre="image")
        if not chemin:
            return None
        try:
            cible = export.enregistrer_figure(figure, chemin)
        except ErreurApplication as erreur:
            self.erreur(erreur)
            return None
        except OSError as erreur:
            journal_app.error("image non écrite : %s", erreur)
            self.erreur(t("fichier.ecriture_impossible", nom=Path(chemin).name))
            return None
        self.info(t("image.enregistree", nom=cible.name))
        return cible

    def exporter(
        self, dossier: str | Path | None = None, nom: str | None = None, formats: tuple[str, ...] | None = None
    ) -> None:
        """Exporte le dernier résultat dans un dossier ; demande confirmation avant d'écraser un fichier."""
        if self.occupe:
            return
        if self.resultat is None:
            self.banniere.afficher(t("erreur.pas_de_resultat"), "alerte")
            return
        choix = self.corps.parametres_export()
        dossier = dossier if dossier is not None else choix.get("dossier", "")
        nom = nom or choix.get("nom") or self.nom_de_base()
        formats = formats if formats is not None else tuple(choix.get("formats", export.FORMATS))
        if not dossier:
            dossier = self.dialogues.choisir_dossier(t("export.choisir"), self.prefs.dossier_export)
        if not dossier:
            return
        resultat = self.resultat
        try:
            existants = export.fichiers_existants(resultat, dossier, nom, formats)
        except ErreurApplication as erreur:
            self.erreur(erreur)
            return
        if existants and not self.confirmer(t("export.confirmer_ecraser", noms=", ".join(existants))):
            return
        self.executer(
            lambda annulation, _avancer: export.exporter(
                resultat, dossier, nom=nom, formats=formats, ecraser=bool(existants), annulation=annulation
            ),
            nom=t("export.nom_tache"),
            au_succes=lambda ecrits: self._export_fini(ecrits, str(dossier)),
        )

    def _export_fini(self, ecrits: list[Path], dossier: str) -> None:
        self.derniers_fichiers = ecrits
        self.prefs.dossier_export = dossier
        self.info(t("export.fait", n=len(ecrits), dossier=diagnostic.anonymiser(dossier)))
        self.corps.mettre_a_jour()

    def ouvrir_dossier_export(self, dossier: str) -> None:
        if dossier and Path(dossier).is_dir() and chemins.ouvrir_dossier(dossier):
            return
        self.erreur(t("export.dossier_absent", dossier=dossier))

    # ====================================================================
    # Affichage : taille, thème, langue
    # ====================================================================
    def _regler_taille(self, pourcentage: int) -> None:
        borne = max(preferences.TAILLE_MIN, min(preferences.TAILLE_MAX, pourcentage))
        self.prefs.taille_police = borne
        self._reappliquer_theme()
        self.statut.set(t("pied.taille", pourcentage=borne))

    def police_plus(self) -> None:
        self._regler_taille(self.prefs.taille_police + 10)

    def police_moins(self) -> None:
        self._regler_taille(self.prefs.taille_police - 10)

    def police_normale(self) -> None:
        self._regler_taille(theme.TAILLE_NORMALE)

    def definir_theme(self, nom: str) -> None:
        self.prefs.theme = nom if nom in theme.PALETTES else "clair"
        self.menus.theme.set(self.prefs.theme)
        self._reappliquer_theme()

    def _reappliquer_theme(self) -> None:
        theme.appliquer(self, self.prefs.theme, self.prefs.taille_police)
        theme.recolorier(self)
        self.zone_journal.colorier()
        self.corps.mettre_a_jour()  # les figures déjà tracées reprennent les couleurs du thème

    def definir_langue(self, code: str) -> None:
        """Change la langue des textes et reconstruit la fenêtre ; entrées, état des écrans et résultat sont gardés."""
        if code not in LANGUES or code == self.langue:
            self.menus.langue.set(self.langue)
            return
        saisies, structure, etat = self.corps.formulaire.brut(), self.corps.saisie_structuree(), self.corps.etat()
        self.langue = definir_langue(code)
        self.prefs.langue = code
        self._construire()
        self.corps.formulaire.definir(saisies)
        self.corps.definir_structure(structure)
        self.corps.restaurer(etat)
        self.corps.mettre_a_jour()
        journal_app.info("langue : %s", code)

    # ====================================================================
    # Aide
    # ====================================================================
    def afficher_guide(self) -> None:
        self.dialogues.info(t("guide.titre"), t("guide.texte"))

    def a_propos(self) -> None:
        self.dialogues.info(
            t("apropos.titre", nom=NOM),
            t(
                "apropos.texte",
                nom=NOM,
                version=__version__,
                licence=LICENCE,
                auteur=AUTEUR,
                annee=ANNEE,
                url=URL_DEPOT,
            ),
        )

    def ouvrir_url(self, url: str) -> bool:
        """Ouvre une page dans le navigateur, sur demande de l'utilisateur : la seule action qui touche au réseau."""
        return bool(webbrowser.open(url))

    def nouvelle_version(self) -> None:
        self.ouvrir_url(URL_RELEASES)

    def page_projet(self) -> None:
        self.ouvrir_url(URL_DEPOT)

    def copier_diagnostic(self) -> None:
        version_tk = str(self.tk.call("info", "patchlevel"))
        self.clipboard_clear()
        self.clipboard_append(diagnostic.diagnostic(self.prefs, version_tk))
        self.info(t("diagnostic.copie"))

    def ouvrir_dossier_journaux(self) -> None:
        if not chemins.ouvrir_dossier(chemins.dossier_journaux()):
            self.erreur(t("erreur.dossier_journaux"))

    # ====================================================================
    # Fin
    # ====================================================================
    def quitter(self) -> None:
        """Arrête le calcul en cours, garde les préférences, ferme la fenêtre."""
        if self._ferme:
            return
        self._ferme = True
        self.pilote.annuler()
        if self._horloge is not None:
            with contextlib.suppress(tk.TclError, ValueError):
                self.after_cancel(self._horloge)
        self.prefs.langue = self.langue
        try:
            preferences.enregistrer(self.prefs)
        except OSError as erreur:
            journal_app.error("préférences non enregistrées : %s", erreur)
        journal_app.info("fermeture")
        self.destroy()


def lancer(flux: journal.FluxInterface | None = None) -> None:
    """Ouvre l'application (point d'entrée de `python -m <paquet>` sans option)."""
    preparer_processus()
    app = Application(flux=flux)
    app.mainloop()
