"""Erreurs de l'application : chaque message est un texte de l'interface, dans la langue choisie."""

from __future__ import annotations

from typing import Any

from ..textes import t

__all__ = [
    "ErreurAnnulation",
    "ErreurApplication",
    "ErreurCalcul",
    "ErreurExport",
    "ErreurSaisie",
]


class ErreurApplication(Exception):
    """Erreur prévue : le message dit le motif et le geste à faire, par une clé de `interface_*.toml`."""

    def __init__(self, cle: str, **champs: Any) -> None:
        self.cle = cle
        self.champs = champs
        super().__init__(t(cle, **champs))


class ErreurSaisie(ErreurApplication):
    """Entrée refusée. `par_champ` donne le message de chaque champ en défaut (nom du champ vers texte)."""

    def __init__(self, cle: str, par_champ: dict[str, str] | None = None, **champs: Any) -> None:
        self.par_champ = dict(par_champ or {})
        super().__init__(cle, **champs)


class ErreurCalcul(ErreurApplication):
    """Le calcul ne peut pas aboutir avec ces entrées."""


class ErreurExport(ErreurApplication):
    """Une sortie ne peut pas être écrite (nom refusé, fichier existant, dossier absent)."""


class ErreurAnnulation(Exception):
    """Le calcul a été interrompu à la demande de l'utilisateur."""

    def __init__(self) -> None:
        super().__init__(t("erreur.annule"))
