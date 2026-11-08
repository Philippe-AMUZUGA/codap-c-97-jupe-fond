# coding: utf-8
"""
Etapes 1 a 3 de C9.7.5 -- sollicitations appliquees au raccordement jupe-appareil.

RAISONNEMENT MECANIQUE
----------------------
Le CODAP ne fait pas entrer les efforts bruts (P, F_Z, M_Z, gradients thermiques)
dans les formules de contrainte : il les convertit d'abord en sept CONTRAINTES DE
REFERENCE R1 a R7, homogenes a des MPa. Chacune represente l'ordre de grandeur de
la contrainte qu'une sollicitation elementaire produirait dans la coque
cylindrique loin de toute discontinuite. Les coefficients Cij de l'Annexe C9.A6
jouent alors le role de facteurs d'amplification locale : ils transportent ces
contraintes « de reference » vers les sections critiques du raccordement.

Cette separation est ce qui rend la regle tabulable : les Rk portent toute la
dependance aux chargements, les Cij toute la dependance a la geometrie.

  R1 -- pression                (C9.7.5-1)
        Contrainte circonferentielle de membrane de la coque, P*D3/(2*eu1).
        C'est la contrainte de « fond » classique. Positive en pression
        interieure, negative en pression exterieure : le signe est porte par P.

  R2 -- effort axial global      (C9.7.5-2)
        2*F_Z/(pi*D3*eu1). Le facteur 2 -- et non 1 -- provient de la convention
        de normalisation retenue par le CODAP pour cette famille de regles : il
        rend R2 directement comparable a R1 (rapport des deux = 4*F_Z/(pi*D3^2*P),
        soit le rapport de l'effort axial a l'effort de pression). F_Z est
        negatif en compression (poids propre + fluide).

  R3 -- moment global de flexion (C9.7.5-3 / -4)
        4*M_Z/(pi*D3^2*eu1), soit la contrainte de flexion en fibre extreme de
        la section annulaire mince. Le SIGNE distingue les deux generatrices :
        positif du cote comprime par M_Z, negatif du cote tendu. La regle doit
        etre appliquee AUX DEUX, car l'interaction avec la pression n'est pas
        symetrique : cote comprime, R1 et R3 s'ajoutent en flexion locale ; cote
        tendu, ils se retranchent, mais la contrainte de membrane resultante peut
        devenir plus penalisante vis-a-vis du critere d'interaction de l'etape 6.

  R4 -- excentrement de la jupe  (C9.7.5-5)
        (c/eu1)*(0,5*R2 + R3). Lorsque la fibre moyenne de la jupe n'est pas
        alignee sur celle de l'enveloppe (ecartement c), les efforts axiaux
        transitant par la jupe induisent un moment de deversement local
        proportionnel a leur excentrement. Noter que le facteur 0,5 porte sur R2
        et NON sur R3 : l'effort axial uniforme est reparti de part et d'autre du
        raccordement, tandis que le moment global s'y applique integralement.

  R5 -- ecart de temperature     (C9.7.5-6 / -7)
        (alpha_K*dT_K - alpha_T*dT_T)*E. Contrainte de bridage due a la
        DIFFERENCE de dilatation libre entre la carre du fond (indice K) et la
        jupe (indice T). Le terme s'annule si les deux parties se dilatent
        identiquement.

  R6 -- gradients dans la paroi  (C9.7.5-8 / -9)
        (alpha_T*g_T + alpha_K*g_K)*E*sqrt(0,5*D3*eu1). Le facteur
        sqrt(0,5*D3*eu1) est la longueur d'attenuation caracteristique d'une
        coque cylindrique : un gradient thermique g [K/mm] ne genere de la
        contrainte que sur cette longueur d'amortissement des perturbations de
        bord. C'est la signature de la theorie des coques minces.

  R7 -- gradient jupe-fond       (C9.7.5-10 / -11)
        (g_K + g_B)*alpha_K*E*sqrt(0,5*D3*eu1). Meme mecanisme, applique au
        couple {carre du fond, bas de la jupe}.

En situation d'epreuve hydraulique, les sollicitations thermiques sont nulles par
construction : R5 = R6 = R7 = 0 (C9.7.5-7, -9, -11).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import (COTE_COMPRIME, COTE_TENDU, COTES, SITUATION_AUTRE,
                     SITUATION_ESSAI, SITUATIONS)

__all__ = ["ReferenceStresses", "compute_reference_stresses"]


@dataclass
class ReferenceStresses:
    """Les sept contraintes de reference de l'etape 3, en MPa."""

    R1: np.ndarray
    R2: np.ndarray
    R3: np.ndarray
    R4: np.ndarray
    R5: np.ndarray
    R6: np.ndarray
    R7: np.ndarray
    cote: str = COTE_COMPRIME
    situation: str = SITUATION_AUTRE
    equations: dict = field(default_factory=dict)

    def as_dict(self):
        return {f"R{i}": getattr(self, f"R{i}") for i in range(1, 8)}


def compute_reference_stresses(data, cote=COTE_COMPRIME, situation=SITUATION_AUTRE):
    """
    Applique l'etape 3 de C9.7.5 a un lot de configurations.

    Parametres
    ----------
    data : mapping nom -> numpy.ndarray
        Doit fournir p, D3, eu1, FZ, MZ, c et, hors situation d'essai,
        deltaTK, deltaTT, alphaK, alphaT, gB, gK, gT, E.
    cote : {'comprime', 'tendu'}
        Cote de la generatrice examinee vis-a-vis du moment global M_Z.
        Fixe le signe de R3 (C9.7.5-3 pour le cote comprime, C9.7.5-4 pour le
        cote tendu).
    situation : {'autre', 'essai'}
        En situation d'essai, les contraintes thermiques sont forcees a zero.

    Retourne
    -------
    ReferenceStresses
    """
    if cote not in COTES:
        raise ValueError(f"cote doit valoir l'un de {COTES}, recu {cote!r}")
    if situation not in SITUATIONS:
        raise ValueError(f"situation doit valoir l'un de {SITUATIONS}, recu {situation!r}")

    # Conversion restreinte aux grandeurs effectivement utilisees : `data` peut
    # porter des colonnes de configuration textuelles ('type_fond', 'situation',
    # 'type_raccordement'), qu'une conversion en bloc ferait echouer.
    requis = ["p", "D3", "eu1", "FZ", "MZ", "c"]
    if situation != SITUATION_ESSAI:
        requis += ["E", "alphaK", "alphaT", "deltaTK", "deltaTT", "gB", "gK", "gT"]
    manquant = [k for k in requis if k not in data]
    if manquant:
        raise KeyError(
            f"grandeurs absentes des donnees d'entree : {manquant} "
            f"(requises pour l'etape 3 en situation {situation!r}).")

    g = {k: np.asarray(data[k], dtype=float) for k in requis}
    p, D3, eu1 = g["p"], g["D3"], g["eu1"]
    FZ, MZ, c = g["FZ"], g["MZ"], g["c"]

    if np.any(eu1 <= 0):
        raise ValueError("eu1 (epaisseur utile de l'enveloppe) doit etre > 0")
    if np.any(D3 <= 0):
        raise ValueError("D3 doit etre > 0")

    # -- C9.7.5-1 : pression -------------------------------------------------
    R1 = p * D3 / (2.0 * eu1)

    # -- C9.7.5-2 : effort axial global --------------------------------------
    R2 = 2.0 * FZ / (np.pi * D3 * eu1)

    # -- C9.7.5-3 / -4 : moment global de flexion ----------------------------
    R3_mag = 4.0 * MZ / (np.pi * D3 ** 2 * eu1)
    signe = 1.0 if cote == COTE_COMPRIME else -1.0
    R3 = signe * R3_mag

    # -- C9.7.5-5 : excentrement de la fibre moyenne de la jupe --------------
    R4 = (c / eu1) * (0.5 * R2 + R3)

    # -- C9.7.5-6 a -11 : sollicitations thermiques --------------------------
    if situation == SITUATION_ESSAI:
        z = np.zeros_like(R1)
        R5, R6, R7 = z, z.copy(), z.copy()
        eqs = {"R5": "C9.7.5-7", "R6": "C9.7.5-9", "R7": "C9.7.5-11"}
    else:
        E = g["E"]
        alphaK, alphaT = g["alphaK"], g["alphaT"]
        dTK, dTT = g["deltaTK"], g["deltaTT"]
        gB, gK, gT = g["gB"], g["gK"], g["gT"]

        # longueur d'attenuation caracteristique de la coque cylindrique
        L_att = np.sqrt(0.5 * D3 * eu1)

        R5 = (alphaK * dTK - alphaT * dTT) * E
        R6 = (alphaT * gT + alphaK * gK) * E * L_att
        R7 = (gK + gB) * alphaK * E * L_att
        eqs = {"R5": "C9.7.5-6", "R6": "C9.7.5-8", "R7": "C9.7.5-10"}

    eqs.update({"R1": "C9.7.5-1", "R2": "C9.7.5-2",
                "R3": "C9.7.5-3" if cote == COTE_COMPRIME else "C9.7.5-4",
                "R4": "C9.7.5-5"})

    return ReferenceStresses(R1=R1, R2=R2, R3=R3, R4=R4, R5=R5, R6=R6, R7=R7,
                             cote=cote, situation=situation, equations=eqs)
