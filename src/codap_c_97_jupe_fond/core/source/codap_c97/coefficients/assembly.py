# coding: utf-8
"""
Etape 4 de C9.7.5 -- assemblage du jeu complet des coefficients Cij.

Le raccordement de type C (appareil pose sur sa jupe) mobilise 42 coefficients,
qui se repartissent en trois categories de provenance distincte. La tracabilite
de cette repartition est essentielle a l'audit : elle indique, pour chaque
coefficient, s'il resulte d'un abaque numerise, d'une forme close, ou d'une
identite entre sections critiques.

  1. TABULES (28) -- issus des abaques de C9.A6.5, evalues par `interp`.
       C21 C31 C51 C61 C81                      (famille A, fonction du fond)
       C22 C32 C52 C62 C82 C92                  (famille B)
       C24 C34 C54 C84
       C25 C35 C55 C65 C85
       C26 C36 C56 C86
       C27 C37 C57 C87

  2. FORMES CLOSES (7) -- donnees explicitement en C9.A6.4-1 a -7 :
       C41 = 0,5/delta2      (C9.A6.4-1)
       C71 = 0,5             (C9.A6.4-2)
       C12 = -0,5/delta1     (C9.A6.4-4)
       C72 = -0,5            (C9.A6.4-5)
       C13 = -1,0/delta1     (C9.A6.4-6)
       C73 = -1,0            (C9.A6.4-7)
     Leur simplicite n'est pas fortuite : ce sont les coefficients d'EQUILIBRE.
     C13 = -1/delta1 et C73 = -1 traduisent la transmission directe du moment
     global M_Z a travers la gorge de soudure et le bord cylindrique, sans
     amplification de coque ; C41 = 0,5/delta2 et C71 = 0,5 traduisent l'effet
     de fond de la pression. Les rapports 1/delta1 rapportent la contrainte a
     l'epaisseur reellement offerte par la section consideree (eu3 au lieu de
     eu1), le facteur d'echelle etant repris ensuite dans les formules de
     l'etape 5 via le rapport eu3/a1.

  3. IDENTITES (7) -- egalites entre coefficients, C9.A6.4-3 et -8 a -14 :
       C91 = C61  (C9.A6.4-3)     C64 = C34  (C9.A6.4-8)
       C94 = C34  (C9.A6.4-9)     C95 = C65  (C9.A6.4-10)
       C66 = C36  (C9.A6.4-11)    C96 = C36  (C9.A6.4-12)
       C67 = C37  (C9.A6.4-13)    C97 = C37  (C9.A6.4-14)
     Elles expriment que, pour ce type de raccordement, la reponse
     circonferentielle des sections critiques 2 et 3 aux sollicitations
     d'excentrement et thermiques est la meme : le fond et le bord cylindrique
     y repondent de facon indissociable.

CAS PARTICULIER : DELTA2 = 1 EN TYPE C
--------------------------------------
delta2 = 1,0 par definition (C9.7.5-17). Il s'ensuit C41 = 0,5 exactement, et
l'interpolation en delta2 de la famille B se reduit a son polynome d'ancrage
z = 1,0 (cf. la note de `interp`). Le mecanisme general est neanmoins conserve.
"""
from __future__ import annotations

import numpy as np

from ..config import FOND_ELLIPTIQUE, FOND_KORBBOGEN, RACCORD_C
from .interp import evaluate_cij

__all__ = ["CoefficientSet", "compute_cij", "COEF_ORDER", "COEF_ORIGIN"]

#: Coefficients evalues par abaque, famille A (dependants du type de fond)
TABULATED_HEAD_DEPENDENT = ("C21", "C31", "C51", "C61", "C81")

#: Coefficients evalues par abaque, famille B (independants du type de fond)
TABULATED_PLAIN = ("C22", "C32", "C52", "C62", "C82", "C92",
                   "C24", "C34", "C54", "C84",
                   "C25", "C35", "C55", "C65", "C85",
                   "C26", "C36", "C56", "C86",
                   "C27", "C37", "C57", "C87")

#: Ordre de restitution, groupe par indice j (colonne de sollicitation)
COEF_ORDER = (
    "C21", "C31", "C41", "C51", "C61", "C71", "C81", "C91",          # j = 1
    "C12", "C22", "C32", "C52", "C62", "C72", "C82", "C92",          # j = 2
    "C13", "C73",                                                     # j = 3
    "C24", "C34", "C54", "C64", "C84", "C94",                        # j = 4
    "C25", "C35", "C55", "C65", "C85", "C95",                        # j = 5
    "C26", "C36", "C56", "C66", "C86", "C96",                        # j = 6
    "C27", "C37", "C57", "C67", "C87", "C97",                        # j = 7
)

#: Provenance reglementaire de chaque coefficient, pour l'audit
COEF_ORIGIN = {
    # formes closes
    "C41": "C9.A6.4-1", "C71": "C9.A6.4-2", "C12": "C9.A6.4-4",
    "C72": "C9.A6.4-5", "C13": "C9.A6.4-6", "C73": "C9.A6.4-7",
    # identites
    "C91": "C9.A6.4-3", "C64": "C9.A6.4-8", "C94": "C9.A6.4-9",
    "C95": "C9.A6.4-10", "C66": "C9.A6.4-11", "C96": "C9.A6.4-12",
    "C67": "C9.A6.4-13", "C97": "C9.A6.4-14",
}
for _c in TABULATED_HEAD_DEPENDENT:
    COEF_ORIGIN[_c] = f"C9.A6.5.{_c[1]}.1"
for _c in TABULATED_PLAIN:
    COEF_ORIGIN[_c] = f"C9.A6.5.{_c[1]}.{_c[2]}"
del _c


class CoefficientSet(dict):
    """
    Jeu complet des coefficients Cij pour un lot de configurations.

    Se comporte comme un dictionnaire nom -> numpy.ndarray, et expose en outre
    les parametres adimensionnels qui l'ont produit.
    """

    def __init__(self, mapping, delta1, delta2, lambda1, head, raccordement):
        super().__init__(mapping)
        self.delta1 = delta1
        self.delta2 = delta2
        self.lambda1 = lambda1
        self.head = head
        self.raccordement = raccordement

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def compute_cij(eu1, eu2, eu3, D1, head=FOND_ELLIPTIQUE, raccordement=RACCORD_C):
    """
    Calcule les 42 coefficients Cij du raccordement type C.

    Parametres
    ----------
    eu1, eu2, eu3 : array_like
        Epaisseurs utiles, en mm : enveloppe (1), jupe (2), fond (3).
    D1 : array_like
        Diametre interieur de l'enveloppe cylindrique, en mm.
    head : {'elliptique', 'korbbogen'}
        Type de fond. Conditionne les seuls coefficients Ci1.
    raccordement : {'C'}
        Type de raccordement. Seul le type C est traite ici.

    Retourne
    -------
    CoefficientSet
    """
    if raccordement != RACCORD_C:
        raise NotImplementedError(
            "Seul le raccordement de type C (appareil pose sur la jupe) est "
            "implemente. Le type AB (appareil emboite) releve de la procedure "
            "C9.A6.3, non couverte par cette version : elle requiert les "
            "coefficients Ci8 a Ci10 et les parametres K1, K2, lambda2."
        )
    if head not in (FOND_ELLIPTIQUE, FOND_KORBBOGEN):
        raise ValueError(
            f"type de fond {head!r} inconnu ; attendu 'elliptique' ou 'korbbogen'. "
            "Le fond torispherique GRC n'est pas admis en raccordement type C "
            "(cf. C9.7.2.1)."
        )

    eu1 = np.asarray(eu1, dtype=float)
    eu2 = np.asarray(eu2, dtype=float)
    eu3 = np.asarray(eu3, dtype=float)
    D1 = np.asarray(D1, dtype=float)

    # -- parametres adimensionnels, C9.7.5-16 a -18 --------------------------
    delta1 = eu3 / eu1                       # C9.7.5-16
    delta2 = np.ones_like(delta1)             # C9.7.5-17 : identiquement 1,0
    lambda1 = D1 / eu2                        # C9.7.5-18

    C = {}

    # -- 1. coefficients tabules --------------------------------------------
    for name in TABULATED_HEAD_DEPENDENT:
        C[name] = evaluate_cij(name, delta1, delta2, lambda1, head=head)
    for name in TABULATED_PLAIN:
        C[name] = evaluate_cij(name, delta1, delta2, lambda1)

    # -- 2. formes closes ----------------------------------------------------
    C["C41"] = 0.5 / delta2                              # C9.A6.4-1
    C["C71"] = np.full_like(delta1, 0.5)                 # C9.A6.4-2
    C["C12"] = -0.5 / delta1                             # C9.A6.4-4
    C["C72"] = np.full_like(delta1, -0.5)                # C9.A6.4-5
    C["C13"] = -1.0 / delta1                             # C9.A6.4-6
    C["C73"] = np.full_like(delta1, -1.0)                # C9.A6.4-7

    # -- 3. identites entre coefficients ------------------------------------
    C["C91"] = C["C61"]          # C9.A6.4-3
    C["C64"] = C["C34"]          # C9.A6.4-8
    C["C94"] = C["C34"]          # C9.A6.4-9
    C["C95"] = C["C65"]          # C9.A6.4-10
    C["C66"] = C["C36"]          # C9.A6.4-11
    C["C96"] = C["C36"]          # C9.A6.4-12
    C["C67"] = C["C37"]          # C9.A6.4-13
    C["C97"] = C["C37"]          # C9.A6.4-14

    missing = set(COEF_ORDER) - set(C)
    if missing:
        raise RuntimeError(f"coefficients manquants apres assemblage : {sorted(missing)}")

    return CoefficientSet({k: C[k] for k in COEF_ORDER},
                          delta1=delta1, delta2=delta2, lambda1=lambda1,
                          head=head, raccordement=raccordement)
