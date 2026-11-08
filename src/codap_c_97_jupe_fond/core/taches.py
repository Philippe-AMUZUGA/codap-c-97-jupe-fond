"""
Calcul dans un fil séparé, avec annulation et suivi, sans aucune dépendance d'interface.

L'interface ne bloque jamais : elle lance une `Tache`, interroge son état à intervalle régulier et peut
demander l'annulation. Le calcul vérifie le jeton d'annulation entre deux unités de travail, jamais au milieu
d'une opération qu'on ne peut pas interrompre proprement. Un jeton, un fil, un résultat :

    tache = Tache(lambda annulation, avancer: calculer(annulation, avancer)).demarrer()
    ...                        # boucle de l'interface : tache.etat, tache.progression()
    tache.annuler()            # demande ; le fil s'arrête à la prochaine vérification
    valeur = tache.resultat()  # lève l'erreur du calcul, ou ErreurAnnulation si annulé

Point d'extension : un calcul long parsème `annulation.verifier()` et `avancer(Progression(...))` entre deux
unités de travail (une ligne, un fichier, un pas).
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from .erreurs import ErreurAnnulation

__all__ = ["Annulation", "EtatTache", "Fonction", "Progression", "Tache"]

T = TypeVar("T")


class EtatTache(StrEnum):
    """Cycle de vie d'une tâche."""

    PRETE = "prete"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    ANNULEE = "annulee"
    ECHEC = "echec"


@dataclass(frozen=True)
class Progression:
    """Avancement d'un calcul : étape en cours, unités faites sur unités prévues."""

    etape: str
    fait: int
    total: int
    message: str = ""

    @property
    def fraction(self) -> float:
        """Part accomplie, entre 0 et 1 (0 si le total est inconnu)."""
        return 0.0 if self.total <= 0 else min(1.0, self.fait / self.total)


class Annulation:
    """Jeton d'annulation, partagé entre l'interface (qui demande) et le calcul (qui vérifie)."""

    def __init__(self) -> None:
        self._evenement = threading.Event()

    def demander(self) -> None:
        """Demande l'arrêt ; sans effet immédiat sur une opération en cours."""
        self._evenement.set()

    @property
    def demandee(self) -> bool:
        return self._evenement.is_set()

    def __call__(self) -> bool:
        """Forme appelable du jeton : vrai si l'arrêt est demandé."""
        return self._evenement.is_set()

    def verifier(self) -> None:
        """Lève `ErreurAnnulation` si l'arrêt a été demandé ; à appeler entre deux unités de travail."""
        if self._evenement.is_set():
            raise ErreurAnnulation


Fonction = Callable[[Annulation, Callable[[Progression], None]], T]


class Tache(Generic[T]):
    """Calcul exécuté dans un fil dédié, annulable, dont l'état se lit sans bloquer.

    La forme `Generic[T]` reste valable de Python 3.11 à 3.13 (la forme `class Tache[T]` demande 3.12).
    """

    def __init__(self, fonction: Fonction[T], nom: str = "calcul") -> None:
        self.nom = nom
        self.annulation = Annulation()
        self._fonction = fonction
        self._verrou = threading.Lock()
        self._fil = threading.Thread(target=self._executer, name=f"tache-{nom}", daemon=True)
        self._etat = EtatTache.PRETE
        self._valeur: T | None = None
        self._erreur: BaseException | None = None
        self._trace = ""
        self._derniere: Progression | None = None
        self._evenements: deque[Progression] = deque(maxlen=1000)

    def demarrer(self) -> Tache[T]:
        """Lance le fil (une seule fois) ; rend la tâche pour chaîner l'appel."""
        with self._verrou:
            if self._etat is not EtatTache.PRETE:
                raise RuntimeError(f"Tâche {self.nom} déjà lancée.")
            self._etat = EtatTache.EN_COURS
        self._fil.start()
        return self

    def annuler(self) -> None:
        """Demande l'annulation ; la tâche passe à ANNULEE quand le calcul s'arrête."""
        self.annulation.demander()

    def _avancer(self, progression: Progression) -> None:
        with self._verrou:
            self._derniere = progression
            self._evenements.append(progression)

    def _executer(self) -> None:
        try:
            valeur = self._fonction(self.annulation, self._avancer)
        except ErreurAnnulation as erreur:
            self._terminer(EtatTache.ANNULEE, erreur=erreur)
        except Exception as erreur:  # le fil ne laisse rien filer : l'erreur est gardée et relue par Tk
            self._terminer(EtatTache.ECHEC, erreur=erreur, trace=traceback.format_exc())
        else:
            self._terminer(EtatTache.TERMINEE, valeur=valeur)

    def _terminer(
        self,
        etat: EtatTache,
        *,
        valeur: T | None = None,
        erreur: BaseException | None = None,
        trace: str = "",
    ) -> None:
        with self._verrou:
            self._valeur, self._erreur, self._trace, self._etat = valeur, erreur, trace, etat

    @property
    def etat(self) -> EtatTache:
        with self._verrou:
            return self._etat

    @property
    def terminee(self) -> bool:
        """Vrai quand le fil a fini, quelle que soit l'issue."""
        return self.etat in (EtatTache.TERMINEE, EtatTache.ANNULEE, EtatTache.ECHEC)

    @property
    def erreur(self) -> BaseException | None:
        with self._verrou:
            return self._erreur

    @property
    def trace(self) -> str:
        """Trace de l'échec, pour le journal (jamais pour l'écran)."""
        with self._verrou:
            return self._trace

    def progression(self) -> Progression | None:
        """Dernier avancement signalé, ou None."""
        with self._verrou:
            return self._derniere

    def evenements(self) -> list[Progression]:
        """Avancements signalés depuis le dernier appel (la liste est vidée)."""
        with self._verrou:
            vus = list(self._evenements)
            self._evenements.clear()
            return vus

    def attendre(self, delai: float | None = None) -> bool:
        """Attend la fin du fil (au plus `delai` secondes) ; vrai si la tâche est terminée."""
        if self._fil.ident is not None:
            self._fil.join(delai)
        return self.terminee

    def resultat(self) -> T:
        """Valeur du calcul ; relève son erreur s'il a échoué, l'erreur d'annulation s'il a été annulé."""
        with self._verrou:
            etat, valeur, erreur = self._etat, self._valeur, self._erreur
        if etat is EtatTache.TERMINEE:
            return valeur  # type: ignore[return-value]
        if erreur is not None:
            raise erreur
        raise RuntimeError(f"Tâche {self.nom} non terminée (état {etat}).")
