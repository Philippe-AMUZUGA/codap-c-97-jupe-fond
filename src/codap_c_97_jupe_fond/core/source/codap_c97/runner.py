# coding: utf-8
"""
Orchestration de la chaine de calcul C9.7.5.

ENCHAINEMENT
------------
    Etape 0  validation.check_application_conditions   conditions C9.7.2
    Etapes 1-2  donnees d'entree (sollicitations fournies par l'Acheteur)
    Etape 3  loads.compute_reference_stresses           R1 a R7
    Etape 4  coefficients.assembly.compute_cij          les 42 Cij
    Etape 5  stresses.compute_stresses                  3 sections critiques
    Etape 6  admissibility.check_admissibility          criteres et verdict

DEUX COTES, UNE ENVELOPPE
-------------------------
Le preambule de C9.7.5 impose d'appliquer la procedure « a la fois du cote tendu
et du cote comprime » par le moment global de flexion. Seul le signe de R3 change
(C9.7.5-3 contre C9.7.5-4), mais ce signe se propage a R4, puis a l'ensemble des
contraintes, et les criteres de l'etape 6 ne sont pas symetriques : le regime de
Tresca (C9.7.5-45 a -48) peut basculer d'un cote a l'autre, faisant passer
sigma_mV de MAX(|.|,|.|) a la SOMME des valeurs absolues, nettement plus
penalisante.

Le programme evalue donc systematiquement les deux cotes et retient l'ENVELOPPE :
la tenue n'est declaree que si les deux cotes sont admissibles, et le taux
d'utilisation restitue est le plus defavorable des deux.
"""
from __future__ import annotations

import numpy as np

from .admissibility import check_admissibility
from .coefficients.assembly import COEF_ORDER, compute_cij
from .config import (COTE_COMPRIME, COTE_TENDU, FOND_ELLIPTIQUE, FONDS,
                     RACCORD_C, RACCORDEMENTS, SITUATION_AUTRE, SITUATIONS)
from .loads import compute_reference_stresses
from .stresses import compute_stresses
from .validation import check_application_conditions, format_report

__all__ = ["run_c975"]


#: Valeurs admissibles de chaque parametre de configuration.
_VALEURS_ADMISES = {
    "type_raccordement": RACCORDEMENTS,
    "type_fond": FONDS,
    "situation": SITUATIONS,
}


def _scalar_config(data, name, default, n):
    """
    Resout un parametre de configuration : colonne du classeur si presente et
    homogene, valeur par defaut sinon.

    La valeur retenue est validee contre la liste des valeurs admissibles. Ce
    controle n'est pas cosmetique : une valeur non reconnue -- ne serait-ce
    qu'une difference de casse -- conduirait sinon a desactiver silencieusement
    des conditions d'application ou a selectionner une branche de calcul
    inattendue. Mieux vaut echouer a la lecture.
    """
    if name not in data:
        valeur = default
    else:
        col = data[name]
        vals = {v for v in col if v is not None}
        if not vals:
            valeur = default
        elif len(vals) > 1:
            raise NotImplementedError(
                f"la colonne {name!r} prend plusieurs valeurs {sorted(vals)} dans "
                "un meme classeur. Cette version traite un type de configuration "
                "par execution : scinder le classeur, ou lancer une execution par "
                "valeur.")
        else:
            valeur = vals.pop()

    admises = _VALEURS_ADMISES.get(name)
    if admises is not None and valeur not in admises:
        raise ValueError(
            f"valeur {valeur!r} non admise pour {name!r} ; attendu l'un de "
            f"{tuple(admises)}. Verifier la casse : le CODAP note les types de "
            "raccordement en majuscules ('AB', 'C'), les types de fond et les "
            "situations en minuscules.")
    return valeur


def run_c975(data, raccordement=RACCORD_C, type_fond=FOND_ELLIPTIQUE,
             situation=SITUATION_AUTRE, verbose=True):
    """
    Deroule la verification C9.7.5 sur un lot de configurations.

    Parametres
    ----------
    data : mapping nom -> ndarray
        Donnees d'entree (cf. `io_excel.read_input_codap`).
    raccordement, type_fond, situation : str
        Configuration par defaut, surchargee par les colonnes homonymes du
        classeur si elles sont presentes.
    verbose : bool
        Affiche le compte-rendu des conditions d'application.

    Retourne
    -------
    dict exploitable par `io_excel.write_output_codap`.
    """
    n = len(data["eu1"])
    raccordement = _scalar_config(data, "type_raccordement", raccordement, n)
    type_fond = _scalar_config(data, "type_fond", type_fond, n)
    situation = _scalar_config(data, "situation", situation, n)

    # ---------------- Etape 0 ----------------------------------------------
    cond = check_application_conditions(data, raccordement=raccordement)
    rapport = format_report(cond)
    if verbose:
        print(rapport)

    # ---------------- Etape 4 (independante du cote) ------------------------
    C = compute_cij(data["eu1"], data["eu2"], data["eu3"], data["D1"],
                    head=type_fond, raccordement=raccordement)

    sides = []
    for cote in (COTE_COMPRIME, COTE_TENDU):
        # -- Etape 3 --------------------------------------------------------
        R = compute_reference_stresses(data, cote=cote, situation=situation)
        # -- Etape 5 --------------------------------------------------------
        SF = compute_stresses(C, R, data["eu3"], data["a1"])
        # -- Etape 6 --------------------------------------------------------
        adm = check_admissibility(SF, data["f"], data["fj"], data["S"], data["phiS"])

        sides.append({
            "cote": cote,
            "R": R.as_dict(),
            "stresses": [s.as_dict() for s in SF],
            "adm": {
                "sigma_m_max1": adm.sigma_m_max1, "ok_membrane_1": adm.ok_membrane_1,
                "v2_1": adm.v2_1, "k1_1": adm.k1_1, "sigma_ball1": adm.sigma_ball1,
                "ok_flexion_1": adm.ok_flexion_1,
                "section_critique": adm.section_critique,
                "sigma_mV": adm.sigma_mV, "v2_23": adm.v2_23, "k1_23": adm.k1_23,
                "sigma_ball": adm.sigma_ball, "ok_flexion_23": adm.ok_flexion_23,
                "ok_global": adm.ok_global, "taux_max": adm.taux_max,
                "critere_determinant": adm.critere_determinant,
                "hors_domaine_interaction": adm.hors_domaine_interaction,
            },
            "_adm_obj": adm,
        })

    # ---------------- enveloppe des deux cotes ------------------------------
    a_comp, a_tend = sides[0]["adm"], sides[1]["adm"]
    ok_env = a_comp["ok_global"] & a_tend["ok_global"]
    taux_comp, taux_tend = a_comp["taux_max"], a_tend["taux_max"]
    pire_comp = taux_comp >= taux_tend
    taux_env = np.where(pire_comp, taux_comp, taux_tend)
    cote_det = np.where(pire_comp, COTE_COMPRIME, COTE_TENDU)
    crit_det = np.where(pire_comp, a_comp["critere_determinant"],
                        a_tend["critere_determinant"])
    hors = (a_comp["hors_domaine_interaction"] | a_tend["hors_domaine_interaction"])

    synthese = {
        "ligne": np.arange(n),
        "D1": data["D1"], "eu1": data["eu1"], "eu2": data["eu2"],
        "eu3": data["eu3"], "a1": data["a1"], "p": data["p"],
        "FZ": data["FZ"], "MZ": data["MZ"],
        "delta1": C.delta1, "lambda1": C.lambda1,
        "dans_domaine_C9A6": cond["dans_domaine"],
        "TENUE": ok_env,
        "verdict": np.array(["TENUE : OK" if v else "TENUE : non-OK" for v in ok_env]),
        "taux_utilisation_max": taux_env,
        "cote_determinant": cote_det,
        "critere_determinant": crit_det,
        "hors_domaine": hors,
        # Le verdict TENUE est un calcul ; il n'est une reponse reglementaire
        # que si les abaques C9.A6 et l'interaction C9.7.5-33 sont dans leur domaine.
        "applicable": cond["dans_domaine"] & ~hors,
    }

    return {
        "sides": sides,
        "Cij": {k: C[k] for k in COEF_ORDER},
        "delta1": C.delta1, "delta2": C.delta2, "lambda1": C.lambda1,
        "synthese": synthese,
        "conditions": cond,
        "rapport_conditions": rapport,
        "config": {"raccordement": raccordement, "type_fond": type_fond,
                   "situation": situation, "n": n},
    }
