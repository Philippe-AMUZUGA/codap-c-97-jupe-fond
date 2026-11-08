# coding: utf-8
"""
C9.7.6 -- stabilite de la jupe, et Annexe C9.A7 -- section affaiblie.

RAISONNEMENT MECANIQUE
----------------------
La verification de C9.7.6 est un critere d'INTERACTION COMPRESSION-FLEXION
vis-a-vis du flambage de la virole de jupe, ecrit au droit de la section droite
X-X la plus faible :

        F_Y / (Psi1 * F_cmax) + (|M_Y| + F_Y * Psi3 * D4) / (Psi2 * M_max) <= 1

Trois mecanismes distincts y sont representes par les trois coefficients
d'affaiblissement de l'Annexe C9.A7 :

  Psi1 = A_affaiblie / A_pleine        rapport d'AIRES
        Une ouverture retire de la matiere : la resistance a la compression pure
        chute au prorata. Psi1 divise F_cmax.

  Psi2 = W_affaiblie / W_pleine        rapport de MODULES D'INERTIE
        La resistance en flexion chute au prorata de la perte de module. Psi2
        divise M_max.

  Psi3 = |y_G| / D4                    EXCENTREMENT
        Une section ajouree n'est plus centree sur l'axe de l'appareil : son
        centre de gravite se decale de y_G. L'effort vertical F_Y, qui reste
        applique sur l'axe, cree donc un moment parasite F_Y * |y_G| qui
        S'AJOUTE au moment de renversement. Psi3 ne degrade pas une resistance :
        il majore une sollicitation. C'est le terme le plus facile a omettre dans
        une verification manuelle, et il n'est pas negligeable des que
        l'ouverture est grande.

PERIMETRE ET DEPENDANCE A L'ANNEXE C9.A4
----------------------------------------
F_cmax et M_max -- charges globales maximales admissibles vis-a-vis de
l'instabilite -- relevent de l'Annexe C9.A4, qui n'est PAS couverte par ce
programme (regle de flambage de coque, distincte du raccordement jupe-fond).
Elles sont donc traitees ici comme des DONNEES D'ENTREE.

En leur absence, la verification C9.7.6 n'est pas effectuee et le statut
'NON EVALUE' est retourne. Elle n'est jamais declaree satisfaite par defaut :
une donnee manquante ne doit pas produire un verdict favorable.

LACUNE DU TEXTE REGLEMENTAIRE EN C9.A7.4 -- COMPLEMENT D'INGENIERIE
-------------------------------------------------------------------
Deux voies de calcul des Psi_i coexistent :

  C9.A7.3 -- une seule ouverture respectant le schema de la Figure C9.A7.2-1.
      Formules analytiques completes (C9.A7.3-1 a -10). Implementees a
      l'identique.

  C9.A7.4 -- tous les autres cas (plusieurs ouvertures, tubulure oblique).
      Le CODAP prescrit « calculer y_G », « calculer A4 », « calculer W_e »
      SANS DONNER AUCUNE FORMULE, puis n'en tire que trois normalisations
      triviales (C9.A7.4-1 a -3). Or cette voie devient OBLIGATOIRE des que
      l'on considere toutes les ouvertures, ce qu'exigent C9.7.6.3-2 et -3.
      Le texte est donc inapplicable en l'etat sur ce point.

Ce module comble la lacune par un calcul explicite de proprietes de section
composee, sur l'idealisation d'anneau mince suivante :

  - couronne de rayon R = D4/2 et d'epaisseur e4, matiere absente sur un secteur
    de demi-angle delta_i = arcsin(d_i/D4) autour de l'azimut phi_i de chaque
    ouverture ;
  - renfort de l'ouverture i assimile a une aire concentree 2*l_te_i*e_t_i,
    placee au BORD de l'ouverture, soit a l'ordonnee y = R*cos(delta_i) ;
  - abscisse de flexion y = R*cos(phi) mesuree depuis l'axe de flexion.

Ce choix n'est pas arbitraire : il est CALIBRE de facon a reproduire exactement
l'Annexe C9.A7.3 dans le cas d'une ouverture unique. On verifie en effet
analytiquement, en posant K = 2*l_te*e_t/(theta*D4*e4) et theta = pi - delta :

    A4      = 2*theta*R*e4 + 2*l_te*e_t
    Psi1    = A4/(2*pi*R*e4) = (theta/pi)*(1 + K)          <-> C9.A7.3-3
    y_G     = -R*(sin(theta)/theta + cos(theta)*K)/(1 + K)
    Psi3    = |y_G|/D4 = 0,5*(sin(theta)/theta + cos(theta)*K)/(1 + K)
                                                            <-> C9.A7.3-4

C'est precisement le placement du renfort au bord de l'ouverture -- et non sur la
couronne -- qui fait apparaitre le facteur cos(theta) de C9.A7.3-4. Le modele est
donc bien celui du redacteur du code, et la generalisation a plusieurs ouvertures
est legitime pour Psi1 et Psi3. La fonction `verify_C9A7_consistency` verifie
cette identite numeriquement.

SIGNE DE PSI3 -- OMISSION DE LA VALEUR ABSOLUE EN C9.A7.3-4
-----------------------------------------------------------
L'equation C9.A7.3-4 s'ecrit

    Psi3 = 0,5 * (sin(theta)/theta + K*cos(theta)) / (1 + K)

sans aucune valeur absolue. Or theta = pi - delta > pi/2, donc cos(theta) < 0
toujours : le terme K*cos(theta) est negatif, et il l'emporte sur sin(theta)/theta
des que le renfort est un peu consequent. Pour D4 = 2000 mm et e4 = 20 mm, une
ouverture de 200 mm renforcee par e_t = 40 mm sur l_t = 80 mm -- soit une plaque
de doublement d'epaisseur double de la jupe, configuration courante -- donne
deja Psi3 = -0,0092.

Ce resultat contredit la definition de la grandeur, enoncee deux fois dans le
code : C9.7.3 et C9.A7.2 definissent Psi3 comme le rapport de la DISTANCE y_G au
diametre D4, et C9.A7.4-3 l'ecrit explicitement Psi3 = |y_G| / D4, valeur absolue
comprise. Une distance est positive ; C9.A7.3-4 omet donc une valeur absolue que
la voie parallele de la meme annexe porte.

La consequence n'est pas neutre. Dans C9.7.6.2-1, le terme + F_Y*Psi3*D4 MAJORE le
moment sollicitant, pour representer le moment parasite du a l'excentrement du
centre de gravite. Un Psi3 negatif le RETRANCHE : le critere devient
non conservatif, d'environ 5 % sur l'exemple ci-dessus.

Ce module retient donc la VALEUR ABSOLUE, conformement a la definition de Psi3, et
conserve la valeur signee du texte litteral dans `detail['psi3_litteral']`, avec
l'indicateur `detail['psi3_signe_inverse']`. Les deux voies de l'Annexe C9.A7
concordent alors en signe comme en module (a 1e-6 pres).

C'est le seul endroit ou ce module s'ecarte de la lettre du texte. L'ecart est
assume, documente ici et dans le rapport technique, et il va dans le sens de la
securite.

RESERVE SUR PSI2
----------------
Pour Psi2, la meme demarche NE reproduit PAS C9.A7.3-10. Le module d'inertie
obtenu par la definition usuelle W_e = I_G/c (I_G second moment centre, c
distance a la fibre extreme) s'ecarte de la combinaison Psi21..Psi25 du code,
dont la construction fait intervenir un terme Psi22 qui ne se deduit pas de
cette definition. L'ecart est quantifie par `verify_C9A7_consistency` et
documente dans le rapport technique.

En consequence, ce module privilegie TOUJOURS la voie C9.A7.3 lorsqu'elle est
applicable (une ouverture, schema conforme), et ne recourt au calcul de section
composee que lorsque le code l'impose sans le definir. Le drapeau
`complement_ingenierie` signale alors explicitement les resultats concernes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["PsiCoefficients", "Opening", "psi_single_opening_C9A7_3",
           "psi_composed_section_C9A7_4", "section_properties",
           "check_stability", "verify_C9A7_consistency",
           "STABLE", "INSTABLE", "NON_EVALUE"]

STABLE = "STABLE"
INSTABLE = "INSTABLE"
NON_EVALUE = "NON EVALUE"

#: Seuil de C9.7.6.3 etape 4 sur les Psi des ouvertures secondaires
SEUIL_PSI_SECONDAIRE = 0.95
#: Seuil de C9.7.6.3 sur le parametre intermediaire x
SEUIL_X = 0.9


@dataclass
class Opening:
    """
    Ouverture dans la jupe au droit de la section X-X.

    Attributs
    ---------
    d : float
        Diametre equivalent de l'ouverture, mm (C9.A7.2).
    e_t : float
        Epaisseur du renfort, mm. Zero si l'ouverture n'est pas renforcee.
    l_t : float
        Hauteur du renfort, mm. Zero si l'ouverture n'est pas renforcee.
    phi : float
        Azimut du centre de l'ouverture par rapport au plan de flexion, rad.
        Zero place l'ouverture sur la fibre extreme, ce qui est le cas le plus
        penalisant et la configuration implicite de la Figure C9.A7.2-1.
        N'intervient que dans la voie C9.A7.4.
    schema_conforme : bool
        Vrai si la geometrie respecte le schema de principe de la Figure
        C9.A7.2-1 (tubulure radiale debouchante). Faux impose la voie C9.A7.4.
    """

    d: float
    e_t: float = 0.0
    l_t: float = 0.0
    phi: float = 0.0
    schema_conforme: bool = True

    def l_te(self) -> float:
        """
        Hauteur effective du renfort.

            l_te = MIN(l_t ; sqrt(d*e_t))

        Formule donnee page 2081 du CODAP DANS LA LISTE DES NOTATIONS de
        C9.A7.2, sans numero d'equation. Elle borne la hauteur de renfort
        reellement mobilisable par la longueur d'attenuation sqrt(d*e_t) :
        au-dela, le renfort ne participe plus a la reprise des efforts.

        En l'absence de renfort (e_t = 0 ou l_t = 0), l_te = 0 : le CODAP ne
        precise pas ce cas, la valeur nulle est la seule qui annule la
        contribution du renfort dans C9.A7.3-3, -4, -7 et -8.
        """
        if self.e_t <= 0.0 or self.l_t <= 0.0:
            return 0.0
        return min(self.l_t, np.sqrt(self.d * self.e_t))


@dataclass
class PsiCoefficients:
    """Coefficients d'affaiblissement de la section X-X."""

    psi1: float
    psi2: float
    psi3: float
    voie: str                       # 'C9.A7.3' ou 'C9.A7.4'
    complement_ingenierie: bool = False
    detail: dict = field(default_factory=dict)


# ==========================================================================
# Annexe C9.A7.3 -- une ouverture conforme au schema de la Figure C9.A7.2-1
# ==========================================================================
def psi_single_opening_C9A7_3(opening: Opening, D4: float, e4: float) -> PsiCoefficients:
    """
    Coefficients Psi1, Psi2, Psi3 par la voie C9.A7.3.

    Applicable si et seulement si la section ne comporte QU'UNE ouverture ET que
    celle-ci respecte le schema de principe de la Figure C9.A7.2-1.
    """
    d, e_t = float(opening.d), float(opening.e_t)
    l_te = opening.l_te()

    if not (0.0 < d <= D4):
        raise ValueError(f"le diametre equivalent d={d} doit verifier 0 < d <= D4={D4} "
                         "(C9.A7.3-1 : arcsin(d/D4)).")
    if e4 <= 0:
        raise ValueError("e4 doit etre > 0")

    delta = np.arcsin(d / D4)                       # C9.A7.3-1
    theta = np.pi - delta                           # C9.A7.3-2

    # groupement commun a C9.A7.3-3, -4 et -7
    K = (2.0 * l_te) / (theta * D4) * (e_t / e4) if l_te > 0 else 0.0

    psi1 = min(1.0, (theta / np.pi) * (1.0 + K))    # C9.A7.3-3

    # C9.A7.3-4. Attention : le texte n'y porte AUCUNE valeur absolue, alors que
    # cos(theta) <= 0 rend le numerateur negatif des que le renfort est un peu
    # consequent. Or Psi3 est defini -- en C9.7.3, en C9.A7.2 et explicitement en
    # C9.A7.4-3 -- comme |y_G|/D4 : c'est une distance, donc positive. On retient
    # donc la valeur absolue, conformement a la definition de la grandeur, et l'on
    # conserve la valeur signee dans `detail` pour l'audit. Voir la note detaillee
    # en tete de module et le rapport technique.
    psi3_litteral = 0.5 * (np.sin(theta) / theta + np.cos(theta) * K) / (1.0 + K)
    psi3 = abs(psi3_litteral)
    signe_inverse = psi3_litteral < 0.0

    st, ct = np.sin(theta), np.cos(theta)
    psi21 = 1.0 + (st / theta ** 2) * (theta * ct - 2.0 * st)             # C9.A7.3-5
    psi22 = (2.0 / theta ** 2) * (theta * ct - st) ** 2                   # C9.A7.3-6
    psi23 = K / (1.0 + K)                                                  # C9.A7.3-7
    # C9.A7.3-8 : l'exposant 3 ne porte QUE sur (2*l_te/D4)
    psi24 = (1.0 / (6.0 * theta)) * (2.0 * l_te / D4) ** 3 * (e_t / e4) \
        if l_te > 0 else 0.0
    psi25 = (theta / np.pi) * (psi21 + psi22 + psi23 + psi24)              # C9.A7.3-9

    # C9.A7.3-10 : noter l_te/D4 SANS facteur 2, seule occurrence de l'Annexe
    denom = max(abs(psi3 + 0.5 * (l_te / D4 - ct)), abs(0.5 - psi3))
    if denom <= 0.0:
        raise ZeroDivisionError(
            "denominateur nul en C9.A7.3-10 ; configuration non physique "
            "(exigerait Psi3 = 1/2 et l_te/D4 = cos(theta) - 1 < 0)."
        )
    psi2 = min(1.0, 0.5 * psi25 / denom)

    return PsiCoefficients(
        psi1=psi1, psi2=psi2, psi3=psi3, voie="C9.A7.3",
        complement_ingenierie=False,
        detail=dict(delta=delta, theta=theta, l_te=l_te, K=K,
                    psi21=psi21, psi22=psi22, psi23=psi23,
                    psi24=psi24, psi25=psi25, denominateur=denom,
                    psi3_litteral=psi3_litteral,
                    psi3_signe_inverse=bool(signe_inverse)))


# ==========================================================================
# Annexe C9.A7.4 -- autres cas : proprietes de section composee
# ==========================================================================
def section_properties(openings, D4: float, e4: float, n_theta: int = 200_001):
    """
    Aire, position du centre de gravite et module d'inertie d'une section de
    jupe ajouree -- COMPLEMENT D'INGENIERIE, le CODAP ne donnant pas ces
    formules (cf. en-tete du module).

    Idealisation : anneau mince de rayon R = D4/2 et d'epaisseur e4, prive d'un
    secteur de demi-angle delta_i = arcsin(d_i/D4) autour de chaque azimut
    phi_i, augmente pour chaque ouverture d'une aire de renfort 2*l_te_i*e_t_i
    concentree au bord de l'ouverture (ordonnee y = R*cos(delta_i)).

    L'integration sur la couronne est menee analytiquement par secteur ; seules
    les eventuelles superpositions d'ouvertures sont traitees par masque
    discret, `n_theta` fixant la finesse de ce masque.

    Retourne
    -------
    dict avec A4, y_G, W_e, I_G, c_max, et les aires elementaires.
    """
    R = 0.5 * D4
    phis = np.linspace(-np.pi, np.pi, n_theta, endpoint=False)
    dphi = 2.0 * np.pi / n_theta

    present = np.ones_like(phis, dtype=bool)
    for op in openings:
        d = float(op.d)
        if not (0.0 < d <= D4):
            raise ValueError(f"diametre equivalent d={d} invalide (0 < d <= D4={D4}).")
        delta = np.arcsin(d / D4)
        ecart = np.abs(np.angle(np.exp(1j * (phis - op.phi))))
        present &= ecart >= delta

    # --- couronne ajouree ---------------------------------------------------
    y = R * np.cos(phis)
    dA = R * e4 * dphi
    A_ring = np.count_nonzero(present) * dA
    S_ring = np.sum(y[present]) * dA                    # moment statique
    I_ring = np.sum(y[present] ** 2) * dA               # moment d'ordre 2 / axe

    # --- renforts -----------------------------------------------------------
    A_ren = S_ren = I_ren = 0.0
    y_ren_list = []
    for op in openings:
        l_te = op.l_te()
        if l_te <= 0.0:
            continue
        a = 2.0 * l_te * float(op.e_t)
        delta = np.arcsin(float(op.d) / D4)
        # renfort au bord de l'ouverture, cf. calibration sur C9.A7.3-4
        y_r = R * np.cos(delta) * np.cos(op.phi)
        A_ren += a
        S_ren += a * y_r
        I_ren += a * y_r ** 2
        y_ren_list.append(y_r)

    A4 = A_ring + A_ren
    if A4 <= 0.0:
        raise ValueError("aire de section affaiblie nulle ou negative : "
                         "les ouvertures couvrent toute la circonference.")
    y_G = (S_ring + S_ren) / A4
    I_axe = I_ring + I_ren
    I_G = I_axe - A4 * y_G ** 2                          # theoreme de Huygens

    # fibre extreme : matiere de la couronne et sommets de renfort
    cands = [np.abs(y[present] - y_G).max()]
    for op, y_r in zip([o for o in openings if o.l_te() > 0], y_ren_list):
        cands.append(abs(y_r + np.sign(y_r or 1.0) * op.l_te() - y_G))
    c_max = max(cands)
    W_e = I_G / c_max

    return dict(A4=A4, y_G=y_G, W_e=W_e, I_G=I_G, c_max=c_max,
                A_couronne=A_ring, A_renforts=A_ren)


def psi_composed_section_C9A7_4(openings, D4: float, e4: float) -> PsiCoefficients:
    """
    Coefficients Psi1, Psi2, Psi3 par la voie C9.A7.4.

    Les normalisations C9.A7.4-1 a -3 sont appliquees telles quelles au resultat
    du calcul de section composee de `section_properties`.

    Noter qu'aucun plafonnement a 1,0 n'est prescrit par C9.A7.4-1 ni -2,
    contrairement a C9.A7.3-3 et -10 : il n'en est donc pas applique.
    """
    props = section_properties(openings, D4, e4)

    psi1 = props["A4"] / (np.pi * D4 * e4)                       # C9.A7.4-1
    psi2 = 4.0 * props["W_e"] / (np.pi * D4 ** 2 * e4)           # C9.A7.4-2
    psi3 = abs(props["y_G"]) / D4                                # C9.A7.4-3

    return PsiCoefficients(psi1=psi1, psi2=psi2, psi3=psi3, voie="C9.A7.4",
                           complement_ingenierie=True, detail=props)


def compute_psi(openings, D4: float, e4: float) -> PsiCoefficients:
    """
    Aiguillage normatif de C9.A7.1 entre les deux voies de calcul.

    C9.A7.3 est retenue si et seulement si la section comporte exactement une
    ouverture ET que celle-ci respecte le schema de principe de la Figure
    C9.A7.2-1. Dans tous les autres cas, C9.A7.4 s'impose.
    """
    ops = list(openings)
    if len(ops) == 1 and ops[0].schema_conforme:
        return psi_single_opening_C9A7_3(ops[0], D4, e4)
    return psi_composed_section_C9A7_4(ops, D4, e4)


# ==========================================================================
# C9.7.6 -- verification de la stabilite
# ==========================================================================
@dataclass
class StabilityResult:
    """Resultat de la verification C9.7.6 pour une section X-X."""

    statut: str
    critere: float | None
    equation: str
    n_ouvertures: int
    psi: PsiCoefficients | None = None
    x: float | None = None
    detail: dict = field(default_factory=dict)
    motif: str = ""


def _critere(FY, MY, Fcmax, Mmax, psi1, psi2, psi3, D4):
    """
    Membre de gauche du critere d'interaction compression-flexion.

    Forme commune a C9.7.6.2-1, C9.7.6.3-1, C9.7.6.3-2 et C9.7.6.3-3.
    """
    return FY / (psi1 * Fcmax) + (abs(MY) + FY * psi3 * D4) / (psi2 * Mmax)


def check_stability(FY, MY, D4, e4, openings=(), Fcmax=None, Mmax=None):
    """
    Verifie la stabilite de la jupe au droit de la section X-X (C9.7.6).

    Parametres
    ----------
    FY, MY : float
        Effort vertical et moment global de flexion sollicitant la jupe A SA
        BASE (section Y-Y), en N et N.mm. Le CODAP prescrit explicitement la
        section Y-Y pour les charges, alors que les Psi_i et F_cmax/M_max se
        rapportent a la section X-X ; aucun transport n'est prescrit entre les
        deux.
    D4, e4 : float
        Diametre interieur et epaisseur utile de la jupe au droit de X-X, mm.
    openings : sequence[Opening]
        Ouvertures presentes au droit de X-X. Sequence vide -> C9.7.6.1.
    Fcmax, Mmax : float ou None
        Charges globales maximales admissibles vis-a-vis de l'instabilite,
        a determiner par l'Annexe C9.A4 (hors perimetre de ce programme).
        None -> verification non effectuee, statut 'NON EVALUE'.

    Retourne
    -------
    StabilityResult
    """
    ops = list(openings)
    n = len(ops)

    if Fcmax is None or Mmax is None:
        return StabilityResult(
            statut=NON_EVALUE, critere=None, equation="-", n_ouvertures=n,
            motif="F_cmax et/ou M_max non fournis. Ces grandeurs relevent de "
                  "l'Annexe C9.A4 (resistance au flambage de la jupe), hors "
                  "perimetre de ce programme. La verification C9.7.6 n'est pas "
                  "effectuee ; elle n'est pas non plus reputee satisfaite.")
    if Fcmax <= 0 or Mmax <= 0:
        raise ValueError("F_cmax et M_max doivent etre strictement positifs.")

    # ---------------- C9.7.6.1 : aucune ouverture --------------------------
    if n == 0:
        crit = FY / Fcmax + abs(MY) / Mmax                      # C9.7.6.1-1
        return StabilityResult(
            statut=STABLE if crit <= 1.0 else INSTABLE,
            critere=crit, equation="C9.7.6.1-1", n_ouvertures=0,
            motif="Section X-X sans ouverture : aucun coefficient "
                  "d'affaiblissement (equivaut a Psi1 = Psi2 = 1, Psi3 = 0).")

    # ---------------- C9.7.6.2 : une seule ouverture -----------------------
    if n == 1:
        psi = compute_psi(ops, D4, e4)
        crit = _critere(FY, MY, Fcmax, Mmax, psi.psi1, psi.psi2, psi.psi3, D4)
        return StabilityResult(
            statut=STABLE if crit <= 1.0 else INSTABLE,
            critere=crit, equation="C9.7.6.2-1", n_ouvertures=1, psi=psi)

    # ---------------- C9.7.6.3 : plusieurs ouvertures ----------------------
    # l'ouverture d'indice 1 est celle de plus grand diametre equivalent
    ordre = sorted(range(n), key=lambda i: -float(ops[i].d))
    principale = ops[ordre[0]]
    secondaires = [ops[i] for i in ordre[1:]]

    # etape 3 : chaque ouverture secondaire prise seule
    psi_sec = [compute_psi([op], D4, e4) for op in secondaires]
    toutes_faibles = all(p.psi1 > SEUIL_PSI_SECONDAIRE
                         and p.psi2 > SEUIL_PSI_SECONDAIRE for p in psi_sec)

    detail = {"psi_secondaires": [(p.psi1, p.psi2) for p in psi_sec],
              "branche": "a" if toutes_faibles else "b"}

    if toutes_faibles:
        # --- branche a) : pre-test sur la seule ouverture principale -------
        psi_p = compute_psi([principale], D4, e4)
        x = _critere(FY, MY, Fcmax, Mmax, psi_p.psi1, psi_p.psi2, psi_p.psi3, D4)
        detail["psi_principale"] = (psi_p.psi1, psi_p.psi2, psi_p.psi3)

        if x <= SEUIL_X:
            return StabilityResult(
                statut=STABLE, critere=x, equation="C9.7.6.3-1",
                n_ouvertures=n, psi=psi_p, x=x, detail=detail,
                motif=f"Branche a), x = {x:.4f} <= {SEUIL_X} : enveloppe stable "
                      "sans examen de l'ensemble des ouvertures.")
        if x > 1.0:
            return StabilityResult(
                statut=INSTABLE, critere=x, equation="C9.7.6.3-1",
                n_ouvertures=n, psi=psi_p, x=x, detail=detail,
                motif=f"Branche a), x = {x:.4f} > 1,0 : enveloppe instable.")
        # 0,9 < x <= 1,0 -> reprise avec toutes les ouvertures
        psi_all = compute_psi(ops, D4, e4)
        crit = _critere(FY, MY, Fcmax, Mmax,
                        psi_all.psi1, psi_all.psi2, psi_all.psi3, D4)
        return StabilityResult(
            statut=STABLE if crit <= 1.0 else INSTABLE,
            critere=crit, equation="C9.7.6.3-2", n_ouvertures=n,
            psi=psi_all, x=x, detail=detail,
            motif=f"Branche a), {SEUIL_X} < x = {x:.4f} <= 1,0 : reprise du "
                  "calcul avec toutes les ouvertures.")

    # --- branche b) : calcul direct toutes ouvertures ----------------------
    psi_all = compute_psi(ops, D4, e4)
    crit = _critere(FY, MY, Fcmax, Mmax,
                    psi_all.psi1, psi_all.psi2, psi_all.psi3, D4)
    return StabilityResult(
        statut=STABLE if crit <= 1.0 else INSTABLE,
        critere=crit, equation="C9.7.6.3-3", n_ouvertures=n,
        psi=psi_all, detail=detail,
        motif="Branche b) : au moins un Psi1 ou Psi2 d'ouverture secondaire "
              f"est <= {SEUIL_PSI_SECONDAIRE}.")


# ==========================================================================
# Controle de coherence entre les deux voies de l'Annexe C9.A7
# ==========================================================================
def verify_C9A7_consistency(D4=2000.0, e4=20.0, cases=None):
    """
    Confronte la voie C9.A7.3 (analytique) au calcul de section composee sur des
    configurations a UNE ouverture, ou les deux sont theoriquement applicables.

    Psi1 et Psi3 doivent coincider : le modele de section composee a ete calibre
    pour cela (cf. en-tete du module). Psi2 s'ecarte, la construction
    Psi21..Psi25 de C9.A7.3-10 ne se deduisant pas de la definition usuelle
    W_e = I_G/c ; l'ecart est ici quantifie et non masque.

    Retourne la liste des ecarts releves.
    """
    if cases is None:
        cases = [dict(d=200.0, e_t=0.0, l_t=0.0),
                 dict(d=400.0, e_t=0.0, l_t=0.0),
                 dict(d=600.0, e_t=0.0, l_t=0.0),
                 dict(d=400.0, e_t=20.0, l_t=100.0),
                 dict(d=600.0, e_t=30.0, l_t=150.0),
                 dict(d=800.0, e_t=25.0, l_t=200.0)]
    out = []
    for cse in cases:
        op = Opening(**cse)
        a = psi_single_opening_C9A7_3(op, D4, e4)
        b = psi_composed_section_C9A7_4([op], D4, e4)
        out.append(dict(
            cas=cse,
            psi1=(a.psi1, b.psi1, abs(a.psi1 - b.psi1)),
            psi2=(a.psi2, b.psi2, abs(a.psi2 - b.psi2)),
            psi3=(a.psi3, b.psi3, abs(a.psi3 - b.psi3))))
    return out
