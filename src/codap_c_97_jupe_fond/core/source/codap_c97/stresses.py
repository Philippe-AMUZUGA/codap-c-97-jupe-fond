# coding: utf-8
"""
Etape 5 de C9.7.5 -- contraintes dans les trois sections critiques.

RAISONNEMENT MECANIQUE
----------------------
Les trois sections critiques (Figure C9.7.5-1) sont celles ou la discontinuite
geometrique jupe-fond concentre la flexion locale :

  Section 1 -- gorge de la soudure de raccordement jupe-appareil.
      C'est la section de raccord proprement dite, d'epaisseur a1 (gorge de
      soudure). Les efforts y transitent intégralement de la jupe vers
      l'enveloppe. Les contraintes y sont mises a l'echelle par le rapport
      eu3/a1 : a la PUISSANCE 1 pour la membrane (C9.7.5-19), au CARRE pour la
      flexion (C9.7.5-20). Cet exposant 2 n'est pas arbitraire : la contrainte de
      flexion varie comme le moment divise par le module d'inertie, soit en
      1/e^2, tandis que la membrane varie en 1/e. Une gorge de soudure sous-
      dimensionnee penalise donc la flexion de facon quadratique -- c'est le
      point de fragilite typique de ce raccordement.

  Section 2 -- fond, cote carre.
      Zone de plus forte courbure meridienne du fond. La contrainte
      longitudinale de membrane s'y reduit au seul effet de fond de la pression
      (C9.7.5-23 : sigma_mx2 = C41*R1), l'effort axial et le moment global etant
      reportes sur les sections 1 et 3. En revanche la flexion y mobilise les
      six sollicitations (C9.7.5-24).

  Section 3 -- fond, cote bord cylindrique.
      Raccord du fond a la partie cylindrique. La membrane longitudinale y
      reprend l'effort axial et le moment global (C9.7.5-27), ce qui en fait la
      section determinante lorsque le moment de renversement domine.

La contrainte circonferentielle de flexion est, dans les trois sections, prise
forfaitairement egale a 0,3 fois la contrainte longitudinale de flexion
(C9.7.5-22, -26, -30). Ce rapport n'est pas un coefficient de Poisson : c'est un
majorant conventionnel issu de la calibration de la regle sur les resultats de
coques. Noter qu'il n'intervient PAS dans les criteres d'admissibilite de
l'etape 6, qui ne retiennent que sigma_bx -- sigma_by est donc calculee a titre
informatif et de completude du champ de contraintes.

Aucune sommation vectorielle n'est faite entre membrane et flexion a ce stade :
les deux composantes restent separees, car l'etape 6 leur applique des criteres
distincts (limitation directe pour la membrane, interaction membrane-flexion
pour la flexion).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import RATIO_FLEXION_CIRCONFERENTIELLE

__all__ = ["SectionStresses", "StressField", "compute_stresses"]


@dataclass
class SectionStresses:
    """Champ de contraintes d'une section critique, en MPa."""

    index: int
    label: str
    sigma_mx: np.ndarray   # longitudinale de membrane
    sigma_bx: np.ndarray   # longitudinale de flexion
    sigma_my: np.ndarray   # circonferentielle de membrane
    sigma_by: np.ndarray   # circonferentielle de flexion
    equations: dict

    def as_dict(self):
        i = self.index
        return {f"sigma_mx{i}": self.sigma_mx, f"sigma_bx{i}": self.sigma_bx,
                f"sigma_my{i}": self.sigma_my, f"sigma_by{i}": self.sigma_by}


@dataclass
class StressField:
    """Les trois sections critiques du raccordement."""

    s1: SectionStresses
    s2: SectionStresses
    s3: SectionStresses

    def __iter__(self):
        return iter((self.s1, self.s2, self.s3))

    def as_dict(self):
        out = {}
        for s in self:
            out.update(s.as_dict())
        return out


def compute_stresses(C, R, eu3, a1):
    """
    Applique l'etape 5 de C9.7.5.

    Parametres
    ----------
    C : mapping nom -> ndarray
        Jeu des coefficients Cij (cf. `coefficients.assembly.compute_cij`).
    R : ReferenceStresses
        Contraintes de reference R1 a R7 (cf. `loads.compute_reference_stresses`).
    eu3 : array_like
        Epaisseur utile du fond, en mm.
    a1 : array_like
        Epaisseur de la gorge de la soudure de raccordement, en mm.

    Retourne
    -------
    StressField
    """
    eu3 = np.asarray(eu3, dtype=float)
    a1 = np.asarray(a1, dtype=float)
    if np.any(a1 <= 0):
        raise ValueError(
            "a1 (gorge de la soudure de raccordement) doit etre strictement "
            "positive : elle apparait au denominateur de C9.7.5-19 et -20."
        )

    r = eu3 / a1              # rapport d'echelle de la section 1
    k = RATIO_FLEXION_CIRCONFERENTIELLE

    # ---------------- Section critique 1 : gorge de soudure ----------------
    sigma_mx1 = (C["C12"] * R.R2 + C["C13"] * R.R3) * r                # C9.7.5-19
    sigma_bx1 = (C["C21"] * R.R1 + C["C22"] * R.R2 + C["C24"] * R.R4
                 + C["C25"] * R.R5 + C["C26"] * R.R6
                 + C["C27"] * R.R7) * r ** 2                            # C9.7.5-20
    sigma_my1 = (C["C31"] * R.R1 + C["C32"] * R.R2 + C["C34"] * R.R4
                 + C["C35"] * R.R5 + C["C36"] * R.R6
                 + C["C37"] * R.R7)                                     # C9.7.5-21
    sigma_by1 = k * sigma_bx1                                           # C9.7.5-22

    s1 = SectionStresses(
        1, "gorge de la soudure de raccordement jupe-appareil",
        sigma_mx1, sigma_bx1, sigma_my1, sigma_by1,
        {"sigma_mx1": "C9.7.5-19", "sigma_bx1": "C9.7.5-20",
         "sigma_my1": "C9.7.5-21", "sigma_by1": "C9.7.5-22"})

    # ---------------- Section critique 2 : fond, cote carre ----------------
    sigma_mx2 = C["C41"] * R.R1                                         # C9.7.5-23
    sigma_bx2 = (C["C51"] * R.R1 + C["C52"] * R.R2 + C["C54"] * R.R4
                 + C["C55"] * R.R5 + C["C56"] * R.R6
                 + C["C57"] * R.R7)                                     # C9.7.5-24
    sigma_my2 = (C["C61"] * R.R1 + C["C62"] * R.R2 + C["C64"] * R.R4
                 + C["C65"] * R.R5 + C["C66"] * R.R6
                 + C["C67"] * R.R7)                                     # C9.7.5-25
    sigma_by2 = k * sigma_bx2                                           # C9.7.5-26

    s2 = SectionStresses(
        2, "fond, cote carre",
        sigma_mx2, sigma_bx2, sigma_my2, sigma_by2,
        {"sigma_mx2": "C9.7.5-23", "sigma_bx2": "C9.7.5-24",
         "sigma_my2": "C9.7.5-25", "sigma_by2": "C9.7.5-26"})

    # ------------ Section critique 3 : fond, cote bord cylindrique ---------
    sigma_mx3 = C["C71"] * R.R1 + C["C72"] * R.R2 + C["C73"] * R.R3     # C9.7.5-27
    sigma_bx3 = (C["C81"] * R.R1 + C["C82"] * R.R2 + C["C84"] * R.R4
                 + C["C85"] * R.R5 + C["C86"] * R.R6
                 + C["C87"] * R.R7)                                     # C9.7.5-28
    sigma_my3 = (C["C91"] * R.R1 + C["C92"] * R.R2 + C["C94"] * R.R4
                 + C["C95"] * R.R5 + C["C96"] * R.R6
                 + C["C97"] * R.R7)                                     # C9.7.5-29
    sigma_by3 = k * sigma_bx3                                           # C9.7.5-30

    s3 = SectionStresses(
        3, "fond, cote bord cylindrique",
        sigma_mx3, sigma_bx3, sigma_my3, sigma_by3,
        {"sigma_mx3": "C9.7.5-27", "sigma_bx3": "C9.7.5-28",
         "sigma_my3": "C9.7.5-29", "sigma_by3": "C9.7.5-30"})

    return StressField(s1, s2, s3)
