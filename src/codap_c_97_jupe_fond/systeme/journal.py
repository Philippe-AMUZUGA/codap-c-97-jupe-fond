"""
Journal de l'application : fichier roulant, flux visible dans l'interface, exceptions toujours attrapées.

`installer()` pose deux gestionnaires sur le journal du paquet : un `RotatingFileHandler` (1 Mo, 3 fichiers de
sauvegarde) dans le dossier des journaux, et une file lue par la zone « Journal » de la fenêtre. Les
exceptions non attrapées (fil principal, fils de calcul) sont écrites au journal avant de remonter à
l'utilisateur, qui voit un bandeau et peut copier le diagnostic.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from .chemins import dossier_journaux

__all__ = [
    "FORMAT",
    "NOM_FICHIER",
    "FluxInterface",
    "desinstaller",
    "fichier_journal",
    "incidents",
    "installer",
    "lignes_recentes",
    "poser_crochets",
]

FORMAT = "%(asctime)s %(levelname)-8s %(name)s : %(message)s"
NOM_FICHIER = "activite.log"
TAILLE_MAX_OCTETS = 1_000_000
SAUVEGARDES = 3
_NOM_RACINE = __name__.split(".")[0]
_MARQUE = "_application_gestionnaire"

#: Messages d'incidents (exceptions non attrapées) à montrer par l'interface, posés depuis n'importe quel fil.
incidents: queue.SimpleQueue[str] = queue.SimpleQueue()


class FluxInterface(logging.Handler):
    """Gestionnaire qui garde les lignes de journal dans une file, lue par la zone du journal de la fenêtre."""

    def __init__(self) -> None:
        super().__init__()
        self.file: queue.SimpleQueue[str] = queue.SimpleQueue()
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s : %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.file.put(self.format(record))
        except Exception:  # un journal ne doit jamais faire échouer l'application
            self.handleError(record)

    def vider(self) -> list[str]:
        """Lignes arrivées depuis le dernier appel (la file est vidée)."""
        lignes: list[str] = []
        while True:
            try:
                lignes.append(self.file.get_nowait())
            except queue.Empty:
                return lignes


def fichier_journal() -> Path:
    """Chemin du fichier de journal courant."""
    return dossier_journaux() / NOM_FICHIER


def installer(*, console: bool = False, niveau: int = logging.INFO) -> FluxInterface:
    """Pose les gestionnaires du journal (sans doublon si on l'appelle deux fois) ; rend le flux visible."""
    racine = logging.getLogger(_NOM_RACINE)
    desinstaller()
    racine.setLevel(niveau)
    racine.propagate = False
    fichier = RotatingFileHandler(
        fichier_journal(), maxBytes=TAILLE_MAX_OCTETS, backupCount=SAUVEGARDES, encoding="utf-8", delay=True
    )
    fichier.setFormatter(logging.Formatter(FORMAT))
    flux = FluxInterface()
    gestionnaires: list[logging.Handler] = [fichier, flux]
    if console:
        sortie = logging.StreamHandler()
        sortie.setFormatter(logging.Formatter(FORMAT))
        gestionnaires.append(sortie)
    for gestionnaire in gestionnaires:
        setattr(gestionnaire, _MARQUE, True)
        racine.addHandler(gestionnaire)
    return flux


def desinstaller() -> None:
    """Retire et ferme les gestionnaires posés par `installer` (les tests et les relances s'en servent)."""
    racine = logging.getLogger(_NOM_RACINE)
    for gestionnaire in list(racine.handlers):
        if getattr(gestionnaire, _MARQUE, False):
            racine.removeHandler(gestionnaire)
            gestionnaire.close()


def lignes_recentes(nombre: int = 60) -> list[str]:
    """Dernières lignes du fichier de journal courant (liste vide s'il n'existe pas encore)."""
    chemin = fichier_journal()
    if not chemin.is_file():
        return []
    try:
        return chemin.read_text(encoding="utf-8", errors="replace").splitlines()[-nombre:]
    except OSError:
        return []


def poser_crochets() -> None:
    """Journalise les exceptions non attrapées du fil principal et des fils de calcul.

    L'exception de rappel de Tk (`report_callback_exception`) est posée par la fenêtre elle-même.
    """
    journal = logging.getLogger(f"{_NOM_RACINE}.exceptions")

    def principal(genre: type[BaseException], valeur: BaseException, trace: TracebackType | None) -> None:
        if issubclass(genre, KeyboardInterrupt):
            sys.__excepthook__(genre, valeur, trace)
            return
        journal.critical("exception non attrapée", exc_info=(genre, valeur, trace))
        incidents.put(f"{genre.__name__} : {valeur}")

    def fil(arguments: threading.ExceptHookArgs) -> None:
        if arguments.exc_type is SystemExit:
            return
        journal.critical(
            "exception non attrapée dans le fil %s",
            getattr(arguments.thread, "name", "?"),
            exc_info=(arguments.exc_type, arguments.exc_value, arguments.exc_traceback),
        )
        incidents.put(f"{arguments.exc_type.__name__} : {arguments.exc_value}")

    sys.excepthook = principal
    threading.excepthook = fil
