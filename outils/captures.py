"""
Captures de la vraie fenêtre de l'application, pour le README et le guide.

Usage, depuis la racine de l'application, sur un poste avec écran :

    python outils/captures.py                 un fichier PNG par écran et par thème, dans docs/images
    python outils/captures.py -o dossier -t clair -l en

La fenêtre est ouverte comme par `-t` (mode d'essai) : exemple chargé comme par son bouton (`examples/exemple.json`,
entrées structurées comprises), calcul réel, puis chaque écran est affiché, sa tâche propre jouée s'il en a une (une
analyse), et photographié à l'écran du poste. Les préférences et les journaux vont dans un dossier
temporaire : les données réelles ne sont pas touchées. Rien n'est téléchargé. La fenêtre se place en avant pendant
la prise de vue : ne touchez ni la souris ni le clavier et ne recouvrez pas la fenêtre jusqu'à la fin.

Les images sont des captures de ce logiciel, sur chemins neutres ; relisez-les une à une avant de les publier
(aucune donnée personnelle ne doit y figurer). Elles s'obtiennent avec Pillow (module `ImageGrab`), déjà installé
avec les bibliothèques de tracé.

Codes : 0 captures écrites, 1 erreur de saisie ou de fichier, 2 Pillow absent, 3 aucun écran disponible, 4 capture vide.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import shutil
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PAQUET = "codap_c_97_jupe_fond"
THEMES = ("clair", "sombre")
LARGEUR_MIN, HAUTEUR_MIN = 400, 250


def analyseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(description="Photographie la vraie fenêtre de l'application.", add_help=False)
    parseur.add_argument(
        "-o", dest="dossier", default=str(RACINE / "docs" / "images"), help="dossier des images (docs/images)"
    )
    parseur.add_argument(
        "-t", dest="themes", choices=("clair", "sombre", "tous"), default="tous", help="thème photographié"
    )
    parseur.add_argument("-l", dest="langue", choices=("fr", "en"), default="fr", help="langue de l'interface")
    parseur.add_argument("-h", action="help", help="cette aide")
    return parseur


def _module(nom: str):
    return importlib.import_module(f"{PAQUET}.{nom}")


def vues(corps) -> list:
    """Vues à photographier : un écran du rail chacune ; écran unique : les entrées, puis les résultats."""
    if corps.nombre_ecrans:
        return [(numero + 1, lambda numero=numero: corps.afficher(numero)) for numero in range(corps.nombre_ecrans)]
    return [
        (1, lambda: corps.defilement.montrer(corps.entrees)),
        (2, lambda: corps.defilement.montrer(corps.resultats)),
    ]


def preparer_la_vue(app, essai) -> None:
    """L'écran affiché est photographié avec sa tâche propre faite (une analyse), bandeau fermé."""
    corps = app.corps
    ecran = corps.ecrans[corps.courant] if getattr(corps, "ecrans", None) else None
    if ecran is not None and corps.accessible(corps.courant) and ecran.lancer():
        essai.attendre_calcul(app, essai.DELAI_ATTENTE_S)
    app.banniere.masquer()


def photographier(app, chemin: Path, grab) -> None:
    """Met la fenêtre en avant, attend un affichage complet, puis enregistre l'image de sa zone à l'écran."""
    app.update_idletasks()
    app.attributes("-topmost", True)
    app.lift()
    for _ in range(5):
        app.update()
        time.sleep(0.12)
    x, y, largeur, hauteur = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
    image = grab(bbox=(x, y, x + largeur, y + hauteur), all_screens=True)
    app.attributes("-topmost", False)
    if image.width < LARGEUR_MIN or image.height < HAUTEUR_MIN:
        raise ValueError(f"capture trop petite ({image.width} x {image.height} pixels)")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    image.save(chemin)


def sortie_en_utf8() -> None:
    """Messages en UTF-8 quelle que soit la page de code de la console ou du tube qui les lit."""
    for flux in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            flux.reconfigure(encoding="utf-8", errors="replace")


def principal(argv: list[str] | None = None) -> int:
    sortie_en_utf8()
    options = analyseur().parse_args(argv)
    try:
        from PIL import ImageGrab
    except ImportError:
        print(
            "Pillow est absent : installez les dépendances de requirements.txt avant de photographier.", file=sys.stderr
        )
        return 2
    sys.path.insert(0, str(RACINE / "src"))
    chemins = _module("systeme.chemins")
    appli, dialogues, essai = _module("ui.app"), _module("ui.dialogues"), _module("essai")
    journal = _module("systeme.journal")
    exemple = chemins.chemin_exemple()
    if exemple is None:
        print("examples/exemple.json est introuvable.", file=sys.stderr)
        return 1
    themes = THEMES if options.themes == "tous" else (options.themes,)
    dossier = Path(options.dossier)
    ecrits: list[Path] = []
    with tempfile.TemporaryDirectory(prefix=f"{PAQUET}_captures_", ignore_cleanup_errors=True) as temporaire:
        chemins.rediriger(temporaire)
        # l'onglet de comparaison EF est photographié avec les fichiers synthétiques du dépôt
        calculs = _module("core.calculs")
        shutil.copytree(RACINE / "examples" / "etude_exemple", calculs.dossier_etude())
        # le dossier d'export affiché sur l'écran Export est un chemin neutre, jamais le dossier personnel
        reglages = _module("systeme.preferences")
        reglages.enregistrer(reglages.Preferences(dossier_export=str(Path(Path.home().anchor) / "Exports")))
        appli.preparer_processus()
        try:
            app = appli.Application(dialogues=dialogues.DialoguesAutomatiques(confirmation=True, dossier=temporaire))
        except tk.TclError as erreur:
            print(f"Aucun écran disponible : {erreur}", file=sys.stderr)
            return 3
        try:
            app.geometry("+30+30")
            app.definir_langue(options.langue)
            app.charger_exemple()  # comme le bouton : formulaire et entrées structurées des écrans
            app.calculer()
            essai.attendre_calcul(app, essai.DELAI_ATTENTE_S)
            if app.resultat is None:
                print(f"Le calcul de l'exemple n'a pas abouti ({app.banniere.texte}).", file=sys.stderr)
                return 1
            for theme in themes:
                app.definir_theme(theme)
                for numero, afficher in vues(app.corps):
                    afficher()
                    preparer_la_vue(app, essai)
                    chemin = dossier / f"fenetre_{numero}_{theme}.png"
                    try:
                        photographier(app, chemin, ImageGrab.grab)
                    except (ValueError, OSError) as erreur:
                        print(f"Capture {chemin.name} refusée : {erreur}", file=sys.stderr)
                        return 4
                    ecrits.append(chemin)
        finally:
            app.quitter()
            journal.desinstaller()  # le fichier de journal doit être fermé avant que le dossier temporaire disparaisse
            chemins.rediriger(None)
    if not ecrits:
        print("Aucune capture n'a été écrite.", file=sys.stderr)
        return 4
    for chemin in ecrits:
        print(f"écrit : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
