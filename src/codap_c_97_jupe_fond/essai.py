"""
Essai automatique (`python -m codap_c_97_jupe_fond -t`) : le parcours complet, sans geste, en moins d'une minute.

Sept étapes numérotées : poste, configuration et journal, textes, entrées de l'exemple, calcul, export, interface.
Les préférences et les journaux de l'essai vont dans un dossier temporaire (les données réelles ne sont pas
touchées) ; les connexions réseau sont refusées pendant l'essai et toute tentative le fait échouer. L'interface
est la vraie fenêtre, pilotée par les mêmes appels que ses boutons : l'exemple chargé (entrées structurées
comprises), le calcul, chaque écran, la tâche propre de chaque étape qui en a une (une analyse : `Ecran.lancer`),
l'enregistrement d'une figure en PNG et en SVG, les thèmes, la taille, la langue, puis l'export. Code de sortie 0
si tout a réussi ; sans écran disponible, l'étape de l'interface est déclarée ignorée (et dite telle), jamais
comptée comme réussie.
"""

from __future__ import annotations

import gc
import json
import logging
import platform
import shutil
import socket
import tempfile
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import NOM, SLUG, __version__
from .core import calculs, export
from .core.entrees import valider_entrees
from .core.fichiers import lire_entrees
from .core.resultat import Resultat
from .systeme import chemins, journal, preferences
from .textes import LANGUES, champs_de, cles, definir_langue, formater_nombre, langue, t

__all__ = ["EssaiIgnore", "attendre_calcul", "bloquer_reseau", "essai_automatique"]

DELAI_ATTENTE_S = 60.0
_POINTS_DE_CONNEXION = (
    (socket.socket, "connect"),
    (socket.socket, "connect_ex"),
    (socket, "create_connection"),
    (socket, "getaddrinfo"),
)
_RACINE = __name__.split(".")[0]


class EssaiIgnore(Exception):
    """Une étape ne peut pas être jouée sur ce poste (par exemple, pas d'écran) : elle est dite ignorée."""


@contextmanager
def bloquer_reseau() -> Iterator[list[str]]:
    """Refuse toute connexion sortante pendant le bloc ; rend la liste des tentatives (vide si aucune)."""
    tentatives: list[str] = []
    originaux = [getattr(objet, nom) for objet, nom in _POINTS_DE_CONNEXION]

    def refuser(*arguments: Any, **options: Any) -> Any:
        tentatives.append(str(arguments[:2]))
        raise OSError("connexion réseau refusée pendant l'essai")

    for objet, nom in _POINTS_DE_CONNEXION:
        setattr(objet, nom, refuser)
    try:
        yield tentatives
    finally:
        for (objet, nom), original in zip(_POINTS_DE_CONNEXION, originaux, strict=True):
            setattr(objet, nom, original)


class Contexte:
    """Ce que les étapes se passent de l'une à l'autre."""

    def __init__(self, dossier: Path, export_dans: Path) -> None:
        self.dossier = dossier
        self.export_dans = export_dans
        self.entrees: dict[str, Any] = {}
        self.resultat: Resultat | None = None
        self.fichiers: list[str] = []


# ====================================================================
# Les étapes : chacune rend une courte précision, ou lève
# ====================================================================
def _poste(_: Contexte) -> str:
    from .__main__ import verifier_poste

    motif = verifier_poste()
    if motif is not None:
        raise RuntimeError(motif)
    return f"Python {platform.python_version()}, Tk {tk.TkVersion}"


def _configuration(contexte: Contexte) -> str:
    fichier = contexte.dossier / "donnees" / "essai_preferences.json"
    prefs = preferences.Preferences(theme="sombre", taille_police=120)
    preferences.ajouter_recent(prefs, fichier)
    preferences.enregistrer(prefs, fichier)
    relues = preferences.charger(fichier)
    if (relues.theme, relues.taille_police, len(relues.recents)) != ("sombre", 120, 1):
        raise RuntimeError("les préférences relues ne sont pas celles qui ont été écrites")
    journal.installer()
    logging.getLogger(f"{_RACINE}.essai").warning("ligne d'essai")
    journal.desinstaller()
    if not journal.fichier_journal().is_file():
        raise RuntimeError("le fichier de journal n'a pas été créé")
    return "préférences et journal dans un dossier temporaire"


def _textes(_: Contexte) -> str:
    ensembles = {code: cles(code) for code in LANGUES}
    reference = ensembles[LANGUES[0]]
    for code, ensemble in ensembles.items():
        if ensemble != reference:
            raise RuntimeError(f"les clés de texte de {code} diffèrent de celles de {LANGUES[0]}")
    avant = langue()
    champs: dict[str, dict[str, frozenset[str]]] = {}
    try:
        for code in LANGUES:
            definir_langue(code)
            if not formater_nombre(1.5):
                raise RuntimeError("nombre non formaté")
            champs[code] = {cle: champs_de(t(cle)) for cle in reference}
    finally:
        definir_langue(avant)
    for cle in sorted(reference):
        if len({champs[code][cle] for code in LANGUES}) != 1:
            raise RuntimeError(f"les champs {{...}} de la clé {cle} diffèrent d'une langue à l'autre")
    return f"{len(reference)} clés, {len(LANGUES)} langues"


def _entrees(contexte: Contexte) -> str:
    chemin = chemins.chemin_exemple()
    if chemin is None:
        raise RuntimeError("le fichier d'exemple est introuvable")
    contexte.entrees = valider_entrees(lire_entrees(chemin))
    return f"{len(contexte.entrees)} entrées valides dans {chemin.name}"


def _calcul(contexte: Contexte) -> str:
    resultat = calculs.calculer(contexte.entrees)
    if not resultat.mesures:
        raise RuntimeError("le calcul ne rend aucune mesure")
    contexte.resultat = resultat
    return f"{len(resultat.mesures)} mesures, {len(resultat.tableaux)} tableau(x), {len(resultat.figures)} figure(s)"


def _export(contexte: Contexte) -> str:
    resultat = contexte.resultat
    if resultat is None:
        raise RuntimeError("pas de résultat à exporter")
    contexte.export_dans.mkdir(parents=True, exist_ok=True)
    ecrits = export.exporter(resultat, contexte.export_dans, nom="essai")
    if not ecrits:
        raise RuntimeError("aucun fichier exporté")
    _verifier_fichiers(ecrits)
    contexte.fichiers = [p.name for p in ecrits]
    return f"{len(ecrits)} fichiers"


def _verifier_fichiers(ecrits: list[Path]) -> None:
    for chemin in ecrits:
        if not chemin.is_file() or chemin.stat().st_size == 0:
            raise RuntimeError(f"{chemin.name} est absent ou vide")
    projet = next((p for p in ecrits if p.name == export.NOM_PROJET), None)
    if projet is not None:
        empreintes = json.loads(projet.read_text(encoding="utf-8"))["fichiers"]
        for chemin in ecrits:
            if chemin != projet and empreintes.get(chemin.name) != export.empreinte_fichier(chemin):
                raise RuntimeError(f"l'empreinte de {chemin.name} ne correspond pas")


def attendre_calcul(app: Any, delai: float) -> None:
    """Fait tourner la boucle Tk jusqu'à la fin du calcul en cours, sans dépasser le délai."""
    fin = time.monotonic() + delai

    def verifier() -> None:
        if not app.occupe or time.monotonic() > fin:
            app.quit()
        else:
            app.after(15, verifier)

    app.after(1, verifier)
    app.mainloop()
    app.update()
    if app.occupe:
        raise TimeoutError(f"calcul encore en cours après {delai:.0f} s")


def jouer_les_etapes(app: Any) -> int:
    """Ouvre chaque écran et lance la tâche propre de chaque étape qui en a une (une analyse) ; rend leur nombre."""
    lancees = 0
    for numero, ecran in enumerate(getattr(app.corps, "ecrans", [])):
        app.corps.afficher(numero)
        app.update()
        if app.corps.accessible(numero) and ecran.lancer():
            attendre_calcul(app, DELAI_ATTENTE_S)
            if app.erreurs_de_rappel or app.banniere.niveau == "bloquant":
                raise RuntimeError(f"la tâche de l'étape {ecran.CLE} a échoué ({app.banniere.texte})")
            lancees += 1
    return lancees


def zones_de_figure(racine: Any) -> list[Any]:
    """Zones de figure de la fenêtre qui portent une figure, dans l'ordre de construction."""
    from .ui.widgets import ZoneFigure

    zones, file = [], [racine]
    while file:
        widget = file.pop(0)
        if isinstance(widget, ZoneFigure) and widget.figure is not None:
            zones.append(widget)
        file.extend(widget.winfo_children())
    return zones


def _enregistrer_une_image(app: Any, dossier: Path) -> int:
    """Enregistre la première figure affichée en PNG puis en SVG, par le même appel que le bouton ; rend le nombre."""
    zones = zones_de_figure(app)
    if not zones:
        return 0
    for nom in ("figure_essai.png", "figure_essai.svg"):
        ecrite = app.enregistrer_figure(zones[0].figure, str(dossier / nom))
        if ecrite is None or not ecrite.is_file() or ecrite.stat().st_size == 0:
            raise RuntimeError(f"image {nom} non enregistrée ({app.banniere.texte})")
    return 2


def _interface(contexte: Contexte) -> str:
    from .ui.app import Application, preparer_processus
    from .ui.dialogues import DialoguesAutomatiques

    preparer_processus()
    dossier = contexte.export_dans / "interface"
    dossier.mkdir(parents=True, exist_ok=True)
    dialogues = DialoguesAutomatiques(confirmation=True, dossier=str(dossier))
    try:
        app = Application(dialogues=dialogues)
    except tk.TclError as erreur:
        if "display" not in str(erreur).lower():  # seul « pas d'écran » est une étape ignorée ; le reste est un échec
            raise
        raise EssaiIgnore(str(erreur)) from None
    try:
        app.charger_exemple()  # comme le bouton : formulaire et entrées structurées des écrans
        app.calculer()
        attendre_calcul(app, DELAI_ATTENTE_S)
        if app.resultat is None:
            raise RuntimeError(f"pas de résultat ({app.banniere.texte})")
        taches = jouer_les_etapes(app)
        images = _enregistrer_une_image(app, dossier)
        app.definir_theme("sombre")
        app.police_plus()
        app.definir_langue("en" if app.langue == "fr" else "fr")
        app.definir_theme("clair")
        app.police_normale()
        app.update()
        app.exporter(dossier=str(dossier), nom="interface")
        attendre_calcul(app, DELAI_ATTENTE_S)
        if len(app.derniers_fichiers) == 0:
            raise RuntimeError(f"pas d'export ({app.banniere.texte})")
        _verifier_fichiers(app.derniers_fichiers)
        if app.erreurs_de_rappel:
            raise RuntimeError(f"exception dans un rappel de l'interface : {app.erreurs_de_rappel[0]}")
        precision = (
            f"style {app.style}, {app.corps.nombre_ecrans} écran(s), {taches} tâche(s) d'étape, "
            f"{images} image(s), {len(app.derniers_fichiers)} fichiers"
        )
    finally:
        app.quitter()
    return precision


ETAPES: tuple[tuple[str, Callable[[Contexte], str]], ...] = (
    ("poste", _poste),
    ("configuration", _configuration),
    ("textes", _textes),
    ("entrees", _entrees),
    ("calcul", _calcul),
    ("export", _export),
    ("interface", _interface),
)


def essai_automatique(sortie: str | None = None, dire: Callable[[str], None] = print) -> int:
    """Joue les sept étapes ; rend 0 si tout a réussi (une étape ignorée est dite telle), 1 sinon."""
    racine = Path(tempfile.mkdtemp(prefix=f"{SLUG}_essai_"))
    export_dans = Path(sortie) if sortie else racine / "export"
    contexte = Contexte(racine, export_dans)
    redirection_initiale = chemins.redirection()
    chemins.rediriger(racine)
    langue_initiale = langue()
    debut = time.monotonic()
    echec: str | None = None
    ignorees = 0
    dire(t("essai.titre", nom=NOM, version=__version__))
    try:
        with bloquer_reseau() as tentatives:
            for rang, (cle, etape) in enumerate(ETAPES, start=1):
                nom = t(f"essai.etape_{cle}")
                tete = f"[{rang}/{len(ETAPES)}] {nom}"
                depart = time.monotonic()
                try:
                    try:
                        precision = etape(contexte)
                    finally:
                        definir_langue(langue_initiale)  # l'étape de l'interface change de langue
                except EssaiIgnore as ignore:
                    ignorees += 1
                    dire(t("essai.ignore", etape=tete, motif=str(ignore)))
                    continue
                except Exception as erreur:
                    echec = f"{tete} : {type(erreur).__name__} : {erreur}"
                    dire(t("essai.echec", etape=tete, motif=f"{type(erreur).__name__} : {erreur}"))
                    break
                dire(
                    t(
                        "essai.reussi",
                        etape=tete,
                        precision=precision,
                        duree=formater_nombre(time.monotonic() - depart, 1),
                    )
                )
            if echec is None and tentatives:
                echec = f"connexion réseau tentée : {tentatives[0]}"
                dire(t("essai.reseau", tentative=tentatives[0]))
    finally:
        definir_langue(langue_initiale)
        journal.desinstaller()
        chemins.rediriger(redirection_initiale)
        shutil.rmtree(racine, ignore_errors=True)
        gc.collect()  # les images de la fenêtre se libèrent ici, dans le fil principal
    duree = formater_nombre(time.monotonic() - debut, 1)
    if echec is not None:
        dire(t("essai.bilan_echec", motif=echec))
        return 1
    dire(t("essai.bilan_ok", n=len(contexte.fichiers), duree=duree, ignorees=ignorees))
    return 0
