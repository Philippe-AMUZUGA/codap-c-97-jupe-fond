# coding: utf-8
"""
Moteur d'evaluation des coefficients Cij -- CODAP 2015 Div.2, Annexe C9.A6.

RAISONNEMENT MECANIQUE
----------------------
Les coefficients Cij sont des fonctions d'influence adimensionnelles : chacun
convertit une sollicitation reduite Rk (contrainte de reference, cf. C9.7.5
etape 3) en une composante de contrainte locale dans une section critique du
raccordement jupe-appareil. Ils encapsulent la reponse en coque du systeme
{fond + enveloppe + jupe}, c'est-a-dire l'effet de flexion locale induit par la
discontinuite geometrique, que l'equilibre de membrane seul ne peut representer.

L'Annexe C9.A6 les fournit non pas en forme close mais sous forme d'un abaque
numerise : pour chaque coefficient, un faisceau de courbes y(x) indexees par un
parametre d'ancrage z. La valeur cherchee s'obtient en deux temps :

  1. ajustement le long de x  : y1 = P1(x) et y2 = P2(x), polynomes de degre 2
     ou 3 fournis par le code, evalues aux deux ancrages z1 et z2 qui encadrent
     le point de calcul ;
  2. interpolation LINEAIRE en z entre ces deux courbes :

         a = (y1 - y2) / (z1 - z2)
         b = y1 - a * z1
         Cij = a * z + b

Deux familles se distinguent (verifiees exhaustivement, cf. rapport technique) :

  Famille A -- coefficients Ci1 (i = 2,3,5,6,8)
      pilote/interpolation : z = delta1 = eu3/eu1   (C9.7.5-16)
      abscisse             : x = lambda1 = D1/eu2   (C9.7.5-18)
      base polynomiale     : puissances de ln(x)
      DEPEND du type de fond (elliptique ou torispherique Korbbogen), car ces
      coefficients portent l'effet de la pression sur la carre du fond.

  Famille B -- coefficients Cij, j >= 2
      pilote/interpolation : z = delta2 = eu2/eu1   (C9.7.5-13)
      abscisse             : x = delta1
      base polynomiale     : puissances de x
      INDEPENDANTS du type de fond : ils traduisent la reponse de la liaison
      cylindre-jupe aux efforts exterieurs, ou la geometrie du fond n'intervient
      pas au premier ordre.

CAS PARTICULIER DU RACCORDEMENT TYPE C
--------------------------------------
Pour un appareil pose sur sa jupe, delta2 = 1,0 par definition (C9.7.5-17).
La famille B se reduit alors exactement a son polynome d'ancrage z1 = 1,0 :

    b = y1 - a*z1  =>  a*z + b = a*1,0 + y1 - a*1,0 = y1

L'interpolation en delta2 est donc inerte pour le type C. Le mecanisme general
est neanmoins conserve ici, d'une part parce qu'il est celui du code, d'autre
part pour permettre l'extension ulterieure au raccordement type AB (appareil
emboite dans la jupe), pour lequel delta2 varie.

EXTRAPOLATION HORS DOMAINE
--------------------------
La derniere tranche de chaque table est non bornee (borne_sup = None). Le code
y prescrit de reprendre les deux ancrages EXTREMES du faisceau, ce qui revient a
extrapoler lineairement la tendance d'ensemble plutot que la pente du dernier
intervalle. Ce choix, propre au CODAP, est reproduit tel quel.

Toutes les evaluations sont vectorisees (numpy) : le programme traite en une
passe un lot de configurations, ce qui est requis par l'usage en etude
parametrique et en confrontation aux calculs par elements finis.
"""
from __future__ import annotations

import numpy as np

from ._tables_C9A6 import CIJ_TABLES

__all__ = ["evaluate_cij", "available_coefficients", "polyval_band"]


def polyval_band(coeffs: tuple, u: np.ndarray) -> np.ndarray:
    """
    Evalue a0 + a1*u + a2*u**2 + ... (ordre croissant des puissances).

    `np.polyval` attend l'ordre decroissant ; on inverse donc la sequence.
    L'evaluation utilise le schema de Horner, numeriquement stable.
    """
    return np.polyval(list(coeffs)[::-1], u)


def _band_index(driver: np.ndarray, bands) -> np.ndarray:
    """
    Indice de la tranche applicable, pour chaque configuration du lot.

    Les tranches sont ordonnees par borne superieure croissante, la derniere
    etant non bornee. La premiere tranche dont la borne superieure n'est pas
    depassee est retenue, ce qui reproduit exactement la cascade
    `if / elif ... / else` du texte reglementaire.
    """
    idx = np.full(driver.shape, len(bands) - 1, dtype=np.intp)
    # parcours en ordre inverse : les tranches basses ecrasent les hautes
    for k in range(len(bands) - 2, -1, -1):
        hi = bands[k][0]
        if hi is None:
            continue
        idx = np.where(driver <= hi, k, idx)
    return idx


def evaluate_cij(name, delta1, delta2, lambda1, head=None):
    """
    Calcule un coefficient Cij pour un lot de configurations.

    Parametres
    ----------
    name : str
        Nom du coefficient, p. ex. 'C21', 'C34'.
    delta1, delta2, lambda1 : array_like
        Parametres adimensionnels de C9.7.5-16 a C9.7.5-18, meme forme.
    head : {'elliptique', 'korbbogen'} ou None
        Type de fond, requis pour la famille A uniquement.

    Retourne
    -------
    numpy.ndarray  -- meme forme que les entrees.
    """
    delta1 = np.asarray(delta1, dtype=float)
    delta2 = np.asarray(delta2, dtype=float)
    lambda1 = np.asarray(lambda1, dtype=float)

    key = name if name in CIJ_TABLES else (name, head)
    if key not in CIJ_TABLES:
        if head is None and any(
            isinstance(k, tuple) and k[0] == name for k in CIJ_TABLES
        ):
            raise KeyError(
                f"Le coefficient {name} depend du type de fond : "
                f"preciser head='elliptique' ou head='korbbogen'."
            )
        raise KeyError(f"Coefficient {name!r} absent des tables de l'Annexe C9.A6.")

    spec = CIJ_TABLES[key]
    drivers = {"delta1": delta1, "delta2": delta2, "lambda1": lambda1}
    z = drivers[spec["driver"]]
    x = drivers[spec["xvar"]]

    if spec["base"] == "log":
        if np.any(x <= 0):
            raise ValueError(
                f"{name}: l'abscisse {spec['xvar']} doit etre strictement "
                f"positive (polynome en ln)."
            )
        u = np.log(x)
    else:
        u = x

    bands = spec["bands"]
    idx = _band_index(z, bands)

    out = np.empty(np.broadcast(z, u).shape, dtype=float)
    for k, (_hi, z1, p1, z2, p2) in enumerate(bands):
        m = idx == k
        if not np.any(m):
            continue
        um = np.broadcast_to(u, out.shape)[m]
        y1 = polyval_band(p1, um)
        y2 = polyval_band(p2, um)
        a = (y1 - y2) / (z1 - z2)
        b = y1 - a * z1
        out[m] = a * np.broadcast_to(z, out.shape)[m] + b
    return out


def available_coefficients():
    """Liste triee des coefficients tabules, avec leur dependance au fond."""
    plain = sorted(k for k in CIJ_TABLES if isinstance(k, str))
    byhead = {}
    for k in CIJ_TABLES:
        if isinstance(k, tuple):
            byhead.setdefault(k[0], []).append(k[1])
    return {"independants_du_fond": plain,
            "dependants_du_fond": {k: sorted(v) for k, v in sorted(byhead.items())}}
