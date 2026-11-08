# coding: utf-8
"""
Etape 0 -- conditions d'application des regles (C9.7.2 et Annexe C9.A6).

Les regles de C9.7.5 sont issues d'un ajustement numerique sur un domaine
geometrique borne. En dehors de ce domaine, les polynomes de l'Annexe C9.A6 ne
sont plus des interpolations mais des EXTRAPOLATIONS, sans garantie. Le programme
ne refuse pas de calculer -- ce serait inexploitable en etude parametrique -- mais
il signale chaque configuration concernee, de sorte qu'aucun resultat hors
domaine ne puisse etre pris pour un resultat valide.

Les bornes retenues sont celles du domaine tabule de l'Annexe C9.A6 :
    0,5 <= delta1 = eu3/eu1 <= 1,3
    30  <= lambda1 = D1/eu2 <= 400
et, pour le raccordement type AB seul, 0 <= lambda2 = h4/eu2 <= 4.

Conditions propres au raccordement type C (appareil pose sur la jupe) :
    delta2 = eu2/eu1 = 1,0 est impose par C9.7.5-17. Le programme verifie donc la
    coherence de eu2 avec eu1, et signale tout ecart : une jupe d'epaisseur
    differente de celle de l'enveloppe sort du cadre de la formulation type C
    telle qu'ecrite dans le code.
    h4 = 0 (pas d'emboitement) et D3 = D4 (continuite de diametre).
"""
from __future__ import annotations

import numpy as np

from .config import (DELTA1_MAX, DELTA1_MIN, LAMBDA1_MAX, LAMBDA1_MIN,
                     RACCORD_C, RACCORDEMENTS)

__all__ = ["check_application_conditions", "format_report"]


def check_application_conditions(data, raccordement=RACCORD_C, tol=1e-9):
    """
    Verifie les conditions d'application, configuration par configuration.

    Retourne un dict de tableaux booleens (True = condition satisfaite), plus
    `dans_domaine`, conjonction de toutes les conditions.
    """
    eu1 = np.asarray(data["eu1"], float)
    eu2 = np.asarray(data["eu2"], float)
    eu3 = np.asarray(data["eu3"], float)
    D1 = np.asarray(data["D1"], float)
    D3 = np.asarray(data["D3"], float)
    D4 = np.asarray(data["D4"], float)
    h4 = np.asarray(data["h4"], float)
    a1 = np.asarray(data["a1"], float)

    delta1 = eu3 / eu1
    delta2 = eu2 / eu1
    lambda1 = D1 / eu2

    # Une valeur de raccordement non reconnue ne doit PAS conduire a sauter
    # silencieusement les conditions propres au type C : elle doit echouer.
    if raccordement not in RACCORDEMENTS:
        raise ValueError(
            f"type de raccordement {raccordement!r} inconnu ; attendu l'un de "
            f"{RACCORDEMENTS}. Refuser plutot que de verifier un jeu incomplet "
            "de conditions d'application.")

    out = {
        "delta1_dans_bornes": (delta1 >= DELTA1_MIN - tol) & (delta1 <= DELTA1_MAX + tol),
        "lambda1_dans_bornes": (lambda1 >= LAMBDA1_MIN - tol) & (lambda1 <= LAMBDA1_MAX + tol),
        "epaisseurs_positives": (eu1 > 0) & (eu2 > 0) & (eu3 > 0) & (a1 > 0),
        "diametres_positifs": (D1 > 0) & (D3 > 0),
    }

    if raccordement == RACCORD_C:
        out["delta2_egal_1"] = np.abs(delta2 - 1.0) <= 1e-6
        out["h4_nul"] = np.abs(h4) <= tol
        out["D3_egal_D4"] = np.abs(D3 - D4) <= 1e-6

    out["dans_domaine"] = np.logical_and.reduce(list(out.values()))
    out["_valeurs"] = {"delta1": delta1, "delta2": delta2, "lambda1": lambda1}
    return out


def format_report(cond, n_max=8):
    """Compte-rendu textuel des conditions d'application."""
    v = cond["_valeurs"]
    n = v["delta1"].size
    lignes = [
        "Conditions d'application (C9.7.2 / Annexe C9.A6)",
        f"  configurations examinees : {n}",
        f"  delta1 = eu3/eu1 : [{v['delta1'].min():.4f} ; {v['delta1'].max():.4f}] "
        f"(domaine tabule [{DELTA1_MIN} ; {DELTA1_MAX}])",
        f"  delta2 = eu2/eu1 : [{v['delta2'].min():.4f} ; {v['delta2'].max():.4f}] "
        f"(type C : 1,0 impose par C9.7.5-17)",
        f"  lambda1 = D1/eu2 : [{v['lambda1'].min():.2f} ; {v['lambda1'].max():.2f}] "
        f"(domaine tabule [{LAMBDA1_MIN} ; {LAMBDA1_MAX}])",
    ]
    for k, val in cond.items():
        if k.startswith("_") or k == "dans_domaine":
            continue
        nb = int(np.count_nonzero(~val))
        etat = "OK" if nb == 0 else f"{nb} configuration(s) en defaut"
        lignes.append(f"    - {k:24s} : {etat}")
        if nb:
            idx = np.flatnonzero(~val)[:n_max]
            lignes.append(f"        lignes concernees : "
                          f"{[int(i) for i in idx]}"
                          f"{' ...' if nb > n_max else ''}")
    nb_hors = int(np.count_nonzero(~cond["dans_domaine"]))
    lignes.append(f"  BILAN : {n - nb_hors}/{n} configurations dans le domaine de validite")
    if nb_hors:
        lignes.append("  ATTENTION : les configurations hors domaine sont calculees mais "
                      "relevent d'une EXTRAPOLATION des abaques C9.A6, sans garantie.")
    return "\n".join(lignes)
