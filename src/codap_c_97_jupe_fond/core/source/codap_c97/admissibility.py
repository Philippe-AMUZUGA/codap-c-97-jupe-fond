# coding: utf-8
"""
Etape 6 de C9.7.5 -- verification de l'admissibilite des contraintes.

RAISONNEMENT MECANIQUE
----------------------
L'etape 6 n'est pas une simple comparaison a une contrainte admissible : elle
met en oeuvre un critere d'INTERACTION MEMBRANE-FLEXION issu de la theorie de
l'analyse limite. Le principe est le suivant.

Une section soumise a la seule flexion plastifie lorsque le moment atteint le
moment plastique, ce qui correspond a une contrainte de flexion elastique
equivalente de 1,5 fois la limite (rapport des modules plastique et elastique
d'une section rectangulaire : 1,5). Mais si la section supporte simultanement un
effort normal, une partie de l'epaisseur est deja consommee par la membrane et la
reserve de flexion diminue. Pour une section rectangulaire, l'interaction est
exactement PARABOLIQUE :

        M/Mp + (N/Np)^2 = 1

d'ou, en posant v2 = N/Np le taux d'utilisation en membrane :

        k1 = 1,5 * (1 - v2^2)                            (C9.7.5-34 / -50)

k1 est donc le coefficient d'amplification admissible de la flexion, compris
entre 1,5 (aucune membrane) et 0 (membrane saturee). La contrainte de flexion
admissible s'en deduit :

        sigma_ball = k1 * MIN(f ; fj) / S                (C9.7.5-35 / -51)

ou S est un coefficient de securite complementaire et MIN(f ; fj) retient la plus
faible des contraintes nominales de calcul du metal de base et du joint soude.

DEUX CRITERES DISTINCTS SELON LA SECTION
----------------------------------------
Section 1 (gorge de soudure) -- la soudure est traitee comme un element de
liaison : on limite d'abord DIRECTEMENT sa contrainte longitudinale de membrane

        sigma_m_max1 = phi_S * MIN(f ; fj)               (C9.7.5-31)
        |sigma_mx1| <= sigma_m_max1                      (C9.7.5-32)

ou phi_S est le coefficient de soudure. Puis on applique l'interaction, avec
v2 bati sur la seule contrainte longitudinale (C9.7.5-33), la soudure etant
sollicitee principalement dans cette direction.

Sections 2 et 3 (fond) -- on retient d'abord la PLUS CRITIQUE des deux, au sens
de la contrainte longitudinale de flexion (C9.7.5-37 a -44), puis on construit
une contrainte EQUIVALENTE de membrane biaxiale (C9.7.5-45 a -48) :

        si sigma_mx * sigma_my >= 0 :  sigma_mV = MAX(|sigma_mx| ; |sigma_my|)
        si sigma_mx * sigma_my <  0 :  sigma_mV = |sigma_mx| + |sigma_my|

C'est exactement le critere de TRESCA en contraintes planes : la contrainte
equivalente est l'etendue des contraintes principales. Lorsque les deux
composantes sont de meme signe, la troisieme principale (nulle, radiale) borne
l'etendue, qui vaut donc la plus grande en valeur absolue ; lorsqu'elles sont de
signes opposes, l'etendue est la somme des valeurs absolues. Ce dernier cas est
le plus penalisant, et c'est typiquement celui du raccordement sous pression
interieure ET moment de renversement, ou la membrane longitudinale devient
compressive du cote sous le vent tandis que la circonferentielle reste tendue.
Il n'y a pas de verification directe de sigma_mV : elle n'intervient qu'a
travers v2 (C9.7.5-49).

DOMAINE DE VALIDITE DU CRITERE -- POINT DE VIGILANCE
----------------------------------------------------
La formule k1 = 1,5*(1 - v2^2) n'a de sens mecanique que pour |v2| <= 1. Au-dela,
la membrane excede a elle seule la capacite de la section et il ne subsiste
AUCUNE reserve de flexion : k1 devient negatif, donc sigma_ball negatif.

Le texte ecrit le critere sous la forme |sigma_bx| <= |sigma_ball|, avec valeur
absolue au second membre. Applique litteralement a un sigma_ball negatif, ce test
redeviendrait permissif -- et d'autant plus permissif que le depassement en
membrane est important, ce qui est mecaniquement inacceptable. Les barres de
valeur absolue du texte doivent donc se comprendre comme une notation defensive
valable dans le domaine |v2| <= 1, et non comme une autorisation d'extrapoler.

Ce module traite donc explicitement le cas |v2| > 1 : k1 est ecrete a zero, le
verdict est force a NON-OK, et l'indicateur `hors_domaine_interaction` est leve
afin que la situation soit signalee et non silencieusement absorbee.

Pour la section 1, ce cas ne peut se produire sans que C9.7.5-32 ait deja echoue :
la reussite de C9.7.5-32 impose |v2| <= S * phi_S, soit 0,84 pour les valeurs
usuelles S = 1,2 et phi_S = 0,7. Le garde-fou est donc surabondant en section 1,
mais necessaire pour les sections 2 et 3, ou aucune limitation directe de la
membrane n'est prescrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import K1_FACTEUR

__all__ = ["AdmissibilityResult", "check_admissibility"]


@dataclass
class AdmissibilityResult:
    """Resultat de l'etape 6 pour un lot de configurations."""

    # --- section critique 1 ------------------------------------------------
    sigma_m_max1: np.ndarray        # C9.7.5-31
    ok_membrane_1: np.ndarray       # C9.7.5-32
    v2_1: np.ndarray                # C9.7.5-33
    k1_1: np.ndarray                # C9.7.5-34
    sigma_ball1: np.ndarray         # C9.7.5-35
    ok_flexion_1: np.ndarray        # C9.7.5-36
    # --- sections critiques 2 et 3 ----------------------------------------
    section_critique: np.ndarray    # 2 ou 3, selon C9.7.5-37 / -41
    sigma_mx: np.ndarray            # C9.7.5-38 / -42
    sigma_my: np.ndarray            # C9.7.5-39 / -43
    sigma_bx: np.ndarray            # C9.7.5-40 / -44
    sigma_mV: np.ndarray            # C9.7.5-46 / -48
    regime_tresca: np.ndarray       # 'max' ou 'somme'
    v2_23: np.ndarray               # C9.7.5-49
    k1_23: np.ndarray               # C9.7.5-50
    sigma_ball: np.ndarray          # C9.7.5-51
    ok_flexion_23: np.ndarray       # C9.7.5-52
    # --- synthese ----------------------------------------------------------
    hors_domaine_interaction: np.ndarray
    ok_global: np.ndarray
    taux_max: np.ndarray
    critere_determinant: np.ndarray
    equations: dict = field(default_factory=dict)


def _interaction(sigma_ref, f_min, S):
    """
    Interaction membrane-flexion : v2, k1, sigma_ball.

    Implemente C9.7.5-33/-34/-35 (section 1) et C9.7.5-49/-50/-51
    (sections 2 et 3), qui sont formellement identiques -- seule differe la
    contrainte de membrane injectee.

    Retourne (v2, k1, sigma_ball, hors_domaine).
    """
    v2 = S * sigma_ref / f_min
    hors_domaine = np.abs(v2) > 1.0
    # ecretage : au-dela de |v2| = 1, aucune reserve de flexion ne subsiste
    v2_eff = np.clip(v2, -1.0, 1.0)
    k1 = K1_FACTEUR * (1.0 - v2_eff ** 2)
    sigma_ball = k1 * f_min / S
    return v2, k1, sigma_ball, hors_domaine


def check_admissibility(stress_field, f, fj, S, phiS):
    """
    Applique l'etape 6 de C9.7.5.

    Parametres
    ----------
    stress_field : StressField
        Champ de contraintes des trois sections critiques (etape 5).
    f, fj : array_like
        Contraintes nominales de calcul du metal de base et du joint soude, MPa.
    S : array_like
        Coefficient de securite complementaire.
    phiS : array_like
        Coefficient de soudure.

    Retourne
    -------
    AdmissibilityResult
    """
    f = np.asarray(f, dtype=float)
    fj = np.asarray(fj, dtype=float)
    S = np.asarray(S, dtype=float)
    phiS = np.asarray(phiS, dtype=float)

    if np.any(S <= 0):
        raise ValueError("le coefficient de securite S doit etre > 0")
    f_min = np.minimum(f, fj)
    if np.any(f_min <= 0):
        raise ValueError("MIN(f ; fj) doit etre > 0")

    s1, s2, s3 = stress_field.s1, stress_field.s2, stress_field.s3

    # ================= a) Section critique 1 ===============================
    sigma_m_max1 = phiS * f_min                                    # C9.7.5-31
    ok_membrane_1 = np.abs(s1.sigma_mx) <= sigma_m_max1            # C9.7.5-32

    v2_1, k1_1, sigma_ball1, hd1 = _interaction(s1.sigma_mx, f_min, S)
    ok_flexion_1 = np.abs(s1.sigma_bx) <= sigma_ball1              # C9.7.5-36
    ok_flexion_1 = ok_flexion_1 & ~hd1

    # ============ b) Sections critiques 2 et 3 : la plus critique ==========
    # C9.7.5-37 : si |sigma_bx2| >= |sigma_bx3| on retient la section 2
    prend_2 = np.abs(s2.sigma_bx) >= np.abs(s3.sigma_bx)
    section_critique = np.where(prend_2, 2, 3)
    sigma_mx = np.where(prend_2, s2.sigma_mx, s3.sigma_mx)         # -38 / -42
    sigma_my = np.where(prend_2, s2.sigma_my, s3.sigma_my)         # -39 / -43
    sigma_bx = np.where(prend_2, s2.sigma_bx, s3.sigma_bx)         # -40 / -44

    # --- contrainte equivalente de membrane (Tresca) -----------------------
    meme_signe = (sigma_mx * sigma_my) >= 0.0                      # C9.7.5-45
    sigma_mV = np.where(
        meme_signe,
        np.maximum(np.abs(sigma_mx), np.abs(sigma_my)),            # C9.7.5-46
        np.abs(sigma_mx) + np.abs(sigma_my),                       # C9.7.5-48
    )
    regime_tresca = np.where(meme_signe, "max", "somme")

    v2_23, k1_23, sigma_ball, hd23 = _interaction(sigma_mV, f_min, S)
    ok_flexion_23 = np.abs(sigma_bx) <= sigma_ball                 # C9.7.5-52
    ok_flexion_23 = ok_flexion_23 & ~hd23

    # ======================= synthese ======================================
    hors_domaine = hd1 | hd23
    ok_global = ok_membrane_1 & ok_flexion_1 & ok_flexion_23

    # taux d'utilisation de chaque critere (1,0 = a la limite)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_mem1 = np.abs(s1.sigma_mx) / sigma_m_max1
        t_flex1 = np.where(sigma_ball1 > 0, np.abs(s1.sigma_bx) / sigma_ball1, np.inf)
        t_flex23 = np.where(sigma_ball > 0, np.abs(sigma_bx) / sigma_ball, np.inf)

    taux = np.stack([t_mem1, t_flex1, t_flex23])
    taux_max = np.max(taux, axis=0)
    noms = np.array(["C9.7.5-32 (membrane section 1)",
                     "C9.7.5-36 (flexion section 1)",
                     "C9.7.5-52 (flexion sections 2/3)"])
    critere_determinant = noms[np.argmax(taux, axis=0)]

    return AdmissibilityResult(
        sigma_m_max1=sigma_m_max1, ok_membrane_1=ok_membrane_1,
        v2_1=v2_1, k1_1=k1_1, sigma_ball1=sigma_ball1, ok_flexion_1=ok_flexion_1,
        section_critique=section_critique,
        sigma_mx=sigma_mx, sigma_my=sigma_my, sigma_bx=sigma_bx,
        sigma_mV=sigma_mV, regime_tresca=regime_tresca,
        v2_23=v2_23, k1_23=k1_23, sigma_ball=sigma_ball,
        ok_flexion_23=ok_flexion_23,
        hors_domaine_interaction=hors_domaine,
        ok_global=ok_global, taux_max=taux_max,
        critere_determinant=critere_determinant,
        equations={
            "sigma_m_max1": "C9.7.5-31", "ok_membrane_1": "C9.7.5-32",
            "v2_1": "C9.7.5-33", "k1_1": "C9.7.5-34",
            "sigma_ball1": "C9.7.5-35", "ok_flexion_1": "C9.7.5-36",
            "section_critique": "C9.7.5-37/-41", "sigma_mV": "C9.7.5-46/-48",
            "v2_23": "C9.7.5-49", "k1_23": "C9.7.5-50",
            "sigma_ball": "C9.7.5-51", "ok_flexion_23": "C9.7.5-52",
        },
    )
