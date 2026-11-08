"""
Validation des entrées complètes : la seule porte d'entrée du calcul, pour la fenêtre, la ligne de commande et l'essai.

Les entrées complètes réunissent les champs du formulaire et les entrées structurées saisies par des écrans dédiés
(un tableau de facteurs, par exemple). Toutes sont déclarées dans `donnees/entrees.toml` et validées par
`schema.valider` ; le domaine peut ajouter un contrôle d'ensemble, entre plusieurs entrées, en écrivant dans
`core/calculs.py` une fonction `verifier_entrees(entrees)` qui lève `ErreurSaisie`. Sans elle, rien de plus.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import calculs
from .schema import Champ, charger_schema, valider

__all__ = ["valider_entrees"]


def valider_entrees(brut: Mapping[str, Any], champs: tuple[Champ, ...] | None = None) -> dict[str, Any]:
    """Entrées typées et bornées (schéma), puis contrôle d'ensemble du domaine s'il existe."""
    valeurs = valider(champs if champs is not None else charger_schema(), brut)
    controle = getattr(calculs, "verifier_entrees", None)
    if callable(controle):
        controle(valeurs)
    return valeurs
