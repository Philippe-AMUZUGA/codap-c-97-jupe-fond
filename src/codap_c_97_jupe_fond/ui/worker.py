"""
Pont entre le fil de calcul du noyau et la boucle Tk.

Tout calcul tourne dans une `Tache` du noyau (un fil, annulable). La boucle Tk n'attend jamais : le `Pilote`
interroge la tâche toutes les 60 ms par `after`, met à jour la barre de progression, puis rend le résultat ou
l'erreur à l'interface, toujours dans le fil de Tk.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

from ..core.erreurs import ErreurAnnulation, ErreurApplication
from ..core.taches import EtatTache, Fonction, Progression, Tache
from ..textes import t

__all__ = ["INTERVALLE_MS", "Pilote", "message_d_erreur"]

INTERVALLE_MS = 60
journal = logging.getLogger(__name__)


def message_d_erreur(erreur: BaseException, etape: str | None = None) -> str:
    """Texte affiché pour une erreur : le motif du noyau, ou un message sobre si l'erreur est imprévue.

    Le détail d'une erreur imprévue (type, trace) va au journal, jamais à l'écran.
    """
    if isinstance(erreur, ErreurApplication):
        return str(erreur)
    if isinstance(erreur, ErreurAnnulation):
        return t("erreur.annule")
    return t("erreur.imprevue", nom=type(erreur).__name__, etape=etape or t("commun.calcul"))


class Pilote:
    """Suit une tâche à la fois et rend la main à l'interface à sa fin."""

    def __init__(
        self,
        racine: tk.Misc,
        sur_progression: Callable[[float, str], None],
        sur_occupation: Callable[[bool], None],
    ) -> None:
        self._racine = racine
        self._sur_progression = sur_progression
        self._sur_occupation = sur_occupation
        self.tache: Tache[Any] | None = None
        self._au_succes: Callable[[Any], None] | None = None
        self._en_echec: Callable[[BaseException], None] | None = None
        self._annulee: Callable[[], None] | None = None

    @property
    def occupe(self) -> bool:
        return self.tache is not None

    def lancer(
        self,
        fonction: Fonction[Any],
        *,
        nom: str,
        au_succes: Callable[[Any], None],
        en_echec: Callable[[BaseException], None],
        si_annulee: Callable[[], None] | None = None,
    ) -> Tache[Any]:
        """Démarre le calcul dans un fil ; `au_succes(valeur)` ou `en_echec(erreur)` s'exécutent dans Tk."""
        if self.tache is not None:
            raise RuntimeError("Un calcul est déjà en cours.")
        self._au_succes, self._en_echec, self._annulee = au_succes, en_echec, si_annulee
        self.tache = Tache(fonction, nom=nom).demarrer()
        self._sur_occupation(True)
        self._sur_progression(0.0, nom)
        self._racine.after(INTERVALLE_MS, self._sonder)
        return self.tache

    def annuler(self) -> None:
        """Demande l'arrêt du calcul ; le fil s'arrête entre deux unités de travail."""
        if self.tache is not None:
            self.tache.annuler()

    def _sonder(self) -> None:
        tache = self.tache
        if tache is None:
            return
        avancement: Progression | None = tache.progression()
        if avancement is not None:
            self._sur_progression(avancement.fraction, avancement.message or avancement.etape)
        if not tache.terminee:
            self._racine.after(INTERVALLE_MS, self._sonder)
            return
        self._terminer(tache)

    def _terminer(self, tache: Tache[Any]) -> None:
        self.tache = None
        self._sur_occupation(False)
        au_succes, en_echec, annulee = self._au_succes, self._en_echec, self._annulee
        self._sur_progression(0.0, "")
        if tache.etat is EtatTache.TERMINEE and au_succes is not None:
            au_succes(tache.resultat())
        elif tache.etat is EtatTache.ANNULEE:
            if annulee is not None:
                annulee()
        elif en_echec is not None:
            erreur = tache.erreur or RuntimeError("Calcul interrompu.")
            if isinstance(erreur, ErreurApplication):  # refus prévu : une ligne suffit
                journal.warning("calcul refusé (%s) : %s", tache.nom, erreur)
            else:
                journal.error("calcul en échec (%s) :\n%s", tache.nom, tache.trace)
            en_echec(erreur)
