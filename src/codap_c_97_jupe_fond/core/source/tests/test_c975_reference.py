# coding: utf-8
"""
Validation de la chaine C9.7.5 -- etapes 0 a 6.

Quatre familles de controles, de portee croissante :

  1. CAS DE REFERENCE grave en dur (ligne 0 de `input_CODAP.xlsx`), verifie a
     la main : les sept contraintes de reference R1 a R7, les parametres
     adimensionnels, un coefficient tabule, les contraintes de membrane des
     trois sections critiques, la section critique retenue et les grandeurs de
     l'interaction membrane-flexion.

  2. COHERENCE DIMENSIONNELLE. C9.7.5 est un jeu de formules homogenes : sous
     similitude geometrique, avec les efforts mis a l'echelle de facon
     coherente, TOUTES les contraintes doivent etre invariantes. C'est le
     controle le plus puissant de la suite, car il teste simultanement les
     etapes 3, 4, 5 et 6 : une seule puissance fausse dans une seule formule
     le fait echouer, alors qu'un cas de reference ponctuel peut la laisser
     passer.

  3. SYMETRIE DES DEUX COTES du moment global (C9.7.5-3 contre C9.7.5-4).

  4. GARDE-FOU du critere d'interaction hors de son domaine |v2| <= 1. C'est le
     point delicat : le texte ecrit |sigma_bx| <= |sigma_ball| et une lecture
     litterale d'un sigma_ball negatif rendrait le critere d'autant plus
     permissif que la membrane est saturee.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runner
from _runner import INPUT_CODAP_REF, assert_proche, assert_vrai

from codap_c97.config import (COTE_COMPRIME, COTE_TENDU, SITUATION_AUTRE,
                              SITUATION_ESSAI)
from codap_c97.io_excel import read_input_codap
from codap_c97.loads import compute_reference_stresses
from codap_c97.runner import run_c975

# ==========================================================================
# Cas de reference : ligne 0 de input_CODAP.xlsx
# ==========================================================================
#: Appareil D1 = 984 mm, epaisseur 8 mm partout, pose sur sa jupe (type C),
#: pression interieure 1 MPa, compression axiale seule (MZ = 0).
CAS_REFERENCE = {
    # -- geometrie (mm)
    "D1": 984.0, "D3": 984.0, "D4": 984.0,
    "eu1": 8.0, "eu2": 8.0, "eu3": 8.0, "a1": 8.0,
    "c": 0.0, "h4": 0.0,
    # -- chargements
    "p": 1.0, "FZ": -741393.3473110502, "MZ": 0.0,
    # -- materiau et coefficients de securite
    "f": 160.667, "fj": 154.667, "S": 1.2, "phiS": 0.7, "E": 196000.0,
    # -- thermique
    "alphaK": 1.15e-5, "alphaT": 1.15e-5,
    "gB": -0.05, "gK": -0.05, "gT": 0.14,
    "deltaTK": 0.0, "deltaTT": 0.0,
}

#: Valeurs attendues, tolerance relative 1e-8
ATTENDU_STRICT = {
    "R1": 61.5,                 # C9.7.5-1
    "R2": -59.95752846,         # C9.7.5-2
    "R3": 0.0,                  # C9.7.5-3
    "R4": 0.0,                  # C9.7.5-5
    "R5": 0.0,                  # C9.7.5-6
    "R6": 12.72693910,          # C9.7.5-8
    "R7": -14.14104345,         # C9.7.5-10
    "delta1": 1.0,              # C9.7.5-16
    "lambda1": 123.0,           # C9.7.5-18
    "C21": -1.21229363,         # C9.A6.5.2.1
    "sigma_mx2": 30.75,         # C9.7.5-23
    "sigma_mx3": 60.72876423,   # C9.7.5-27
}

#: Valeurs attendues de l'etape 6, tolerance relative 1e-3.
#: Mises a jour le 2026-11-08 apres l'alignement de C92 (delta2 = 1) sur deux calculs independants :
#: avec la constante -0,039 (au lieu de +0,039), sigma_my3 change de 0,073 x |R2| (4,4 MPa dans ce cas
#: ou |R2| = 60 MPa), ce qui fait passer sigma_mV de 80,74 a 76,06 MPa ; le verdict reste « tenue ».
ATTENDU_ETAPE6 = {
    "sigma_m_max1": 108.2669,   # C9.7.5-31
    "sigma_mV": 76.0636,        # C9.7.5-46/-48
    "v2_23": 0.5901,            # C9.7.5-49
    "k1_23": 0.97759,           # C9.7.5-50
    "sigma_ball": 126.0006,     # C9.7.5-51
    "taux_max": 0.9276,         # taux d'utilisation enveloppe
}

#: Toutes les grandeurs qui sont des LONGUEURS dans CAS_REFERENCE
LONGUEURS = ("D1", "D3", "D4", "eu1", "eu2", "eu3", "a1", "c", "h4")
#: Gradients thermiques, en K/mm : grandeurs par unite de LONGUEUR
GRADIENTS = ("gB", "gK", "gT")


def _cas(**surcharges):
    """Construit un lot d'une configuration a partir du cas de reference."""
    d = dict(CAS_REFERENCE)
    d.update(surcharges)
    return {k: np.array([float(v)]) for k, v in d.items()}


def _res(data, situation=SITUATION_AUTRE):
    return run_c975(data, situation=situation, verbose=False)


def _cote(resultat, cote):
    for side in resultat["sides"]:
        if side["cote"] == cote:
            return side
    raise AssertionError(f"cote {cote!r} absent du resultat")


# ==========================================================================
# 1. Cas de reference
# ==========================================================================
def test_reference_contraintes_R1_a_R7():
    """C9.7.5-1 a -10 : les sept contraintes de reference du cas grave en dur."""
    side = _cote(_res(_cas()), COTE_COMPRIME)
    for k in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert_proche(side["R"][k], ATTENDU_STRICT[k], rtol=1e-8, atol=1e-12,
                      nom=k, ref=side["R"].get("equations", {}).get(k, ""))


def test_reference_parametres_adimensionnels_et_C21():
    """C9.7.5-16, -18 et C9.A6.5.2.1 : delta1, lambda1 et le coefficient C21."""
    res = _res(_cas())
    assert_proche(res["delta1"], ATTENDU_STRICT["delta1"], rtol=1e-8,
                  nom="delta1", ref="C9.7.5-16")
    assert_proche(res["delta2"], 1.0, rtol=0.0, atol=0.0,
                  nom="delta2", ref="C9.7.5-17")
    assert_proche(res["lambda1"], ATTENDU_STRICT["lambda1"], rtol=1e-8,
                  nom="lambda1", ref="C9.7.5-18")
    assert_proche(res["Cij"]["C21"], ATTENDU_STRICT["C21"], rtol=1e-8,
                  nom="C21", ref="C9.A6.5.2.1 (fond elliptique)")


def test_reference_contraintes_de_membrane_sections_2_et_3():
    """C9.7.5-23 et -27 : membranes longitudinales du fond, carre et bord."""
    side = _cote(_res(_cas()), COTE_COMPRIME)
    s2, s3 = side["stresses"][1], side["stresses"][2]
    assert_proche(s2["sigma_mx2"], ATTENDU_STRICT["sigma_mx2"], rtol=1e-8,
                  nom="sigma_mx2", ref="C9.7.5-23")
    assert_proche(s3["sigma_mx3"], ATTENDU_STRICT["sigma_mx3"], rtol=1e-8,
                  nom="sigma_mx3", ref="C9.7.5-27")
    # C9.7.5-23 : sigma_mx2 = C41*R1 avec C41 = 0,5 (delta2 = 1)
    assert_proche(s2["sigma_mx2"], 0.5 * ATTENDU_STRICT["R1"], rtol=1e-12,
                  nom="sigma_mx2 = 0,5*R1", ref="C9.7.5-23 / C9.A6.4-1")


def test_reference_etape6_interaction_et_verdict():
    """C9.7.5-31 a -52 : section critique retenue, interaction et TENUE."""
    res = _res(_cas())
    side = _cote(res, COTE_COMPRIME)
    adm = side["adm"]
    assert_vrai(int(adm["section_critique"][0]) == 3,
                f"C9.7.5-37/-41 : section critique 3 attendue "
                f"(|sigma_bx3| >= |sigma_bx2|), obtenu {adm['section_critique'][0]}")
    for k, ref in (("sigma_m_max1", "C9.7.5-31"), ("sigma_mV", "C9.7.5-46/-48"),
                   ("v2_23", "C9.7.5-49"), ("k1_23", "C9.7.5-50"),
                   ("sigma_ball", "C9.7.5-51")):
        assert_proche(adm[k], ATTENDU_ETAPE6[k], rtol=1e-3, nom=k, ref=ref)
    syn = res["synthese"]
    assert_vrai(bool(syn["TENUE"][0]) is True,
                f"TENUE : OK attendue, obtenu {syn['verdict'][0]!r}")
    assert_proche(syn["taux_utilisation_max"], ATTENDU_ETAPE6["taux_max"],
                  rtol=1e-3, nom="taux_utilisation_max",
                  ref="enveloppe des deux cotes")
    assert_vrai(not bool(syn["hors_domaine"][0]),
                "le cas de reference ne doit pas etre signale hors domaine "
                "d'interaction (|v2| <= 1)")
    # coherence interne de C9.7.5-50 et -51
    v2, k1 = float(adm["v2_23"][0]), float(adm["k1_23"][0])
    assert_proche(k1, 1.5 * (1.0 - v2 ** 2), rtol=1e-12,
                  nom="k1 = 1,5*(1-v2^2)", ref="C9.7.5-50")
    f_min = min(CAS_REFERENCE["f"], CAS_REFERENCE["fj"])
    assert_proche(adm["sigma_ball"], k1 * f_min / CAS_REFERENCE["S"], rtol=1e-12,
                  nom="sigma_ball = k1*MIN(f;fj)/S", ref="C9.7.5-51")


def test_reference_est_bien_la_ligne_0_du_classeur():
    """Tracabilite : le cas grave en dur est la ligne 0 de input_CODAP.xlsx."""
    assert_vrai(INPUT_CODAP_REF.exists(),
                f"classeur de reference introuvable : {INPUT_CODAP_REF}")
    data, meta = read_input_codap(INPUT_CODAP_REF)
    assert_vrai(meta["n"] == 117,
                f"117 configurations attendues, {meta['n']} lue(s)")
    for nom, attendu in CAS_REFERENCE.items():
        lu = float(np.asarray(data[nom], float)[0])
        assert_proche(lu, attendu, rtol=1e-12, atol=1e-12,
                      nom=f"colonne {nom}, ligne 0",
                      ref="tracabilite du cas de reference")


# ==========================================================================
# 2. Coherence dimensionnelle -- CONTROLE LE PLUS PUISSANT DE LA SUITE
# ==========================================================================
def _echelle(facteur, avec_gradients=True):
    """
    Applique une similitude geometrique de rapport `facteur`.

    Mise a l'echelle coherente des sollicitations :
        longueurs        x lambda
        F_Z (force)      x lambda^2   (contrainte inchangee : F/(D*e))
        M_Z (moment)     x lambda^3   (contrainte inchangee : M/(D^2*e))
        p (pression)     inchangee    (deja une contrainte)
        g (gradients)    / lambda     grandeur en K/mm, donc par unite de
                                      longueur ; c'est l'echelle qui rend
                                      R6 et R7 invariants (C9.7.5-8 et -10,
                                      ou g est multiplie par la longueur
                                      d'attenuation sqrt(0,5*D3*eu1))
        deltaT, E, alpha, f, fj, S, phiS  inchanges
    """
    d = dict(CAS_REFERENCE)
    for k in LONGUEURS:
        d[k] = CAS_REFERENCE[k] * facteur
    d["FZ"] = CAS_REFERENCE["FZ"] * facteur ** 2
    d["MZ"] = CAS_REFERENCE["MZ"] * facteur ** 3
    if avec_gradients:
        for k in GRADIENTS:
            d[k] = CAS_REFERENCE[k] / facteur
    return {k: np.array([float(v)]) for k, v in d.items()}


def _toutes_les_contraintes(resultat):
    """Aplatit R1..R7, les 12 contraintes des 3 sections et l'etape 6."""
    out = {}
    for side in resultat["sides"]:
        tag = side["cote"]
        for k, v in side["R"].items():
            out[f"{tag}/{k}"] = float(np.asarray(v, float)[0])
        for s in side["stresses"]:
            for k, v in s.items():
                out[f"{tag}/{k}"] = float(np.asarray(v, float)[0])
        for k in ("sigma_m_max1", "v2_1", "k1_1", "sigma_ball1",
                  "sigma_mV", "v2_23", "k1_23", "sigma_ball", "taux_max"):
            out[f"{tag}/{k}"] = float(np.asarray(side["adm"][k], float)[0])
    return out


def test_COHERENCE_DIMENSIONNELLE_invariance_des_contraintes():
    """
    C9.7.5 dans son ensemble : invariance sous similitude geometrique.

    Toutes les longueurs multipliees par lambda, F_Z par lambda^2, M_Z par
    lambda^3, p inchangee, gradients thermiques divises par lambda : les
    parametres adimensionnels delta1, delta2, lambda1 sont invariants, donc les
    42 Cij aussi, et TOUTES les contraintes de C9.7.5 doivent etre rigoureusement
    inchangees -- de meme que v2, k1, sigma_ball et le taux d'utilisation.

    Une seule puissance fausse dans une seule des formules des etapes 3, 5 ou 6
    fait echouer ce controle, y compris lorsqu'un cas de reference ponctuel
    passerait.
    """
    reference = _toutes_les_contraintes(_res(_cas()))
    for facteur in (0.25, 0.5, 2.0, 7.3, 40.0):
        mis_a_l_echelle = _toutes_les_contraintes(_res(_echelle(facteur)))
        assert_vrai(set(reference) == set(mis_a_l_echelle),
                    "le jeu de grandeurs restituees change avec l'echelle")
        for nom, attendu in reference.items():
            assert_proche(mis_a_l_echelle[nom], attendu, rtol=1e-11, atol=1e-11,
                          nom=f"{nom} (lambda = {facteur})",
                          ref="coherence dimensionnelle de C9.7.5")
    # les parametres adimensionnels doivent eux aussi etre invariants
    for facteur in (0.5, 7.3):
        r = _res(_echelle(facteur))
        assert_proche(r["delta1"], ATTENDU_STRICT["delta1"], rtol=1e-12,
                      nom="delta1", ref="C9.7.5-16")
        assert_proche(r["lambda1"], ATTENDU_STRICT["lambda1"], rtol=1e-12,
                      nom="lambda1", ref="C9.7.5-18")


def test_COHERENCE_DIMENSIONNELLE_gradients_non_mis_a_l_echelle():
    """
    C9.7.5-8 et -10 : R6 et R7 sont proportionnels a sqrt(0,5*D3*eu1).

    Complement du controle precedent, qui isole le role des gradients. Si les
    gradients g [K/mm] sont laisses INCHANGES pendant que les longueurs sont
    multipliees par lambda, alors R6 et R7 -- et eux seuls parmi R1 a R7 --
    doivent etre multiplies EXACTEMENT par lambda, la longueur d'attenuation de
    la coque variant comme sqrt(D3*eu1) = lambda*sqrt(D3_0*eu1_0).

    Ce n'est pas un defaut : c'est la signature dimensionnelle correcte d'un
    gradient exprime par unite de longueur. Le controle verifie que le programme
    la respecte au sens strict.
    """
    ref = _cote(_res(_cas()), COTE_COMPRIME)["R"]
    for facteur in (0.5, 2.0, 7.3):
        side = _cote(_res(_echelle(facteur, avec_gradients=False)), COTE_COMPRIME)
        for k in ("R1", "R2", "R3", "R4", "R5"):
            assert_proche(side["R"][k], ref[k], rtol=1e-11, atol=1e-11,
                          nom=f"{k} (lambda = {facteur}, g inchanges)",
                          ref="C9.7.5-1 a -6 : independants de sqrt(D3*eu1)")
        for k in ("R6", "R7"):
            assert_proche(side["R"][k], np.asarray(ref[k], float) * facteur,
                          rtol=1e-11, atol=1e-11,
                          nom=f"{k} (lambda = {facteur}, g inchanges)",
                          ref="C9.7.5-8 et -10 : proportionnels a "
                              "sqrt(0,5*D3*eu1)")


# ==========================================================================
# 3. Symetrie / dissymetrie des deux cotes du moment global
# ==========================================================================
def test_symetrie_des_deux_cotes_sans_moment_global():
    """C9.7.5-3 contre -4 : a M_Z = 0, les deux cotes sont identiques."""
    res = _res(_cas(MZ=0.0, c=0.0))
    comprime = _toutes_les_contraintes(res)
    for nom, valeur in comprime.items():
        if not nom.startswith(COTE_COMPRIME + "/"):
            continue
        homologue = nom.replace(COTE_COMPRIME + "/", COTE_TENDU + "/", 1)
        assert_proche(comprime[homologue], valeur, rtol=0.0, atol=1e-12,
                      nom=nom.split("/", 1)[1],
                      ref="C9.7.5-3 / -4 : symetrie a M_Z = 0")
    # R3 nul des deux cotes
    for cote in (COTE_COMPRIME, COTE_TENDU):
        assert_proche(_cote(res, cote)["R"]["R3"], 0.0, rtol=0.0, atol=0.0,
                      nom="R3", ref="C9.7.5-3 / -4 a M_Z = 0")


def test_dissymetrie_des_deux_cotes_avec_moment_global():
    """C9.7.5-3 contre -4 : a M_Z != 0, R3 change de signe et les cotes different."""
    # M_Z modere et excentrement c non nul : les deux cotes restent dans le
    # domaine |v2| <= 1, ce qui permet de comparer des taux finis.
    res = _res(_cas(MZ=5.0e7, c=10.0))
    comp, tend = _cote(res, COTE_COMPRIME), _cote(res, COTE_TENDU)

    r3c = float(np.asarray(comp["R"]["R3"], float)[0])
    r3t = float(np.asarray(tend["R"]["R3"], float)[0])
    assert_vrai(r3c > 0.0, f"C9.7.5-3 : R3 doit etre positif cote comprime, "
                           f"obtenu {r3c}")
    assert_vrai(r3t < 0.0, f"C9.7.5-4 : R3 doit etre negatif cote tendu, "
                           f"obtenu {r3t}")
    assert_proche(r3t, -r3c, rtol=1e-14, nom="R3 (tendu) = -R3 (comprime)",
                  ref="C9.7.5-3 contre C9.7.5-4")
    # l'etape 3 doit tracer la bonne reference d'equation pour chaque cote
    data = _cas(MZ=5.0e7, c=10.0)
    eq_comp = compute_reference_stresses(data, cote=COTE_COMPRIME).equations["R3"]
    eq_tend = compute_reference_stresses(data, cote=COTE_TENDU).equations["R3"]
    assert_vrai(eq_comp == "C9.7.5-3" and eq_tend == "C9.7.5-4",
                "la reference d'equation de R3 doit distinguer les deux cotes, "
                f"obtenu {eq_comp!r} (comprime) et {eq_tend!r} (tendu)")

    # C9.7.5-5 : le signe de R3 se propage a R4 des que c != 0
    r4c = float(np.asarray(comp["R"]["R4"], float)[0])
    r4t = float(np.asarray(tend["R"]["R4"], float)[0])
    assert_vrai(abs(r4c - r4t) > 1e-9,
                f"C9.7.5-5 : R4 devrait differer entre les cotes (c = 10 mm), "
                f"obtenu {r4c} et {r4t}")

    # les taux d'utilisation doivent differer : c'est ce qui justifie
    # l'examen des DEUX cotes prescrit par le preambule de C9.7.5
    tc = float(np.asarray(comp["adm"]["taux_max"], float)[0])
    tt = float(np.asarray(tend["adm"]["taux_max"], float)[0])
    assert_vrai(abs(tc - tt) > 1e-6,
                f"les deux cotes devraient donner des taux differents a "
                f"M_Z != 0, obtenu {tc:.6f} et {tt:.6f}")
    # l'enveloppe retenue est bien le plus defavorable des deux
    syn = res["synthese"]
    assert_proche(syn["taux_utilisation_max"], max(tc, tt), rtol=1e-14,
                  nom="taux enveloppe", ref="preambule de C9.7.5")
    attendu = COTE_COMPRIME if tc >= tt else COTE_TENDU
    assert_vrai(str(syn["cote_determinant"][0]) == attendu,
                f"cote determinant {attendu!r} attendu, obtenu "
                f"{syn['cote_determinant'][0]!r}")


def test_bascule_du_regime_de_Tresca_entre_les_deux_cotes():
    """C9.7.5-45 a -48 : le regime de Tresca peut basculer d'un cote a l'autre."""
    res = _res(_cas(MZ=4.0e8, c=10.0))
    regimes = {side["cote"]: str(side["_adm_obj"].regime_tresca[0])
               for side in res["sides"]}
    assert_vrai(set(regimes.values()) == {"max", "somme"},
                "C9.7.5-45 : un cas ou le regime de Tresca bascule entre les "
                f"deux cotes etait attendu, obtenu {regimes}")
    # verification de la definition elle-meme, cote par cote
    for side in res["sides"]:
        adm = side["_adm_obj"]
        mx = float(np.asarray(adm.sigma_mx, float)[0])
        my = float(np.asarray(adm.sigma_my, float)[0])
        mV = float(np.asarray(adm.sigma_mV, float)[0])
        if mx * my >= 0.0:
            assert_proche(mV, max(abs(mx), abs(my)), rtol=1e-14,
                          nom="sigma_mV", ref="C9.7.5-46 (meme signe)")
        else:
            assert_proche(mV, abs(mx) + abs(my), rtol=1e-14,
                          nom="sigma_mV", ref="C9.7.5-48 (signes opposes)")


# ==========================================================================
# 4. Situation d'essai
# ==========================================================================
def test_situation_essai_annule_R5_R6_R7():
    """C9.7.5-7, -9 et -11 : en situation d'essai, R5 = R6 = R7 = 0."""
    normal = _cote(_res(_cas(), situation=SITUATION_AUTRE), COTE_COMPRIME)
    essai = _cote(_res(_cas(), situation=SITUATION_ESSAI), COTE_COMPRIME)
    equations = compute_reference_stresses(
        _cas(), cote=COTE_COMPRIME, situation=SITUATION_ESSAI).equations
    for k, ref in (("R5", "C9.7.5-7"), ("R6", "C9.7.5-9"), ("R7", "C9.7.5-11")):
        assert_proche(essai["R"][k], 0.0, rtol=0.0, atol=0.0, nom=k, ref=ref)
        assert_vrai(equations[k] == ref,
                    f"la reference d'equation de {k} en situation d'essai "
                    f"devrait etre {ref}, obtenu {equations[k]!r}")
    # R6 et R7 etaient non nuls en situation normale : l'annulation est reelle
    for k in ("R6", "R7"):
        assert_vrai(abs(float(np.asarray(normal["R"][k], float)[0])) > 1.0,
                    f"le cas de reference devrait avoir {k} non negligeable "
                    "en situation normale, sans quoi le controle est vide")
    # les sollicitations mecaniques R1 a R4 sont inchangees
    for k in ("R1", "R2", "R3", "R4"):
        assert_proche(essai["R"][k], normal["R"][k], rtol=0.0, atol=1e-12,
                      nom=k, ref="C9.7.5-1 a -5 : independantes de la situation")
    # controle direct sur l'etape 3, hors orchestration
    R = compute_reference_stresses(_cas(), cote=COTE_TENDU,
                                  situation=SITUATION_ESSAI)
    for k in ("R5", "R6", "R7"):
        assert_proche(getattr(R, k), 0.0, rtol=0.0, atol=0.0, nom=k,
                      ref="C9.7.5-7 / -9 / -11")


# ==========================================================================
# 5. Garde-fou du critere d'interaction
# ==========================================================================
def test_garde_fou_interaction_hors_domaine_v2_superieur_a_1():
    """
    C9.7.5-49 a -52 : hors du domaine |v2| <= 1, k1 est ecrete a 0 et le
    verdict est force a non-OK.

    La formule k1 = 1,5*(1 - v2^2) devient negative pour |v2| > 1, donc
    sigma_ball negatif. Le texte ecrivant le critere sous la forme
    |sigma_bx| <= |sigma_ball|, une lecture LITTERALE avec sigma_ball negatif
    redeviendrait permissive -- et d'autant plus permissive que le depassement
    en membrane est important, ce qui est mecaniquement inacceptable.

    Cas construit : meme geometrie que le cas de reference, mais pression
    portee a 20 MPa. La membrane du fond sature alors largement la section,
    sans qu'aucune limitation directe de membrane ne soit prescrite pour les
    sections 2 et 3 (contrairement a la section 1, protegee par C9.7.5-32).
    """
    res = _res(_cas(p=20.0))
    for side in res["sides"]:
        adm, obj = side["adm"], side["_adm_obj"]
        v2 = float(np.asarray(adm["v2_23"], float)[0])
        k1 = float(np.asarray(adm["k1_23"], float)[0])
        ball = float(np.asarray(adm["sigma_ball"], float)[0])
        bx = float(np.asarray(obj.sigma_bx, float)[0])

        assert_vrai(abs(v2) > 1.0,
                    f"cote {side['cote']} : le cas doit produire |v2| > 1 pour "
                    f"que le controle ait un sens, obtenu v2 = {v2:.4f}")
        # 1) k1 ecrete a zero, et non negatif
        assert_proche(k1, 0.0, rtol=0.0, atol=0.0, nom="k1_23",
                      ref="C9.7.5-50 ecrete a |v2| = 1")
        assert_proche(ball, 0.0, rtol=0.0, atol=0.0, nom="sigma_ball",
                      ref="C9.7.5-51 avec k1 = 0")
        # 2) le critere n'est PAS satisfait, alors qu'une lecture litterale de
        #    |sigma_bx| <= |sigma_ball| avec sigma_ball < 0 l'aurait rendu
        #    d'autant plus permissif
        assert_vrai(not bool(adm["ok_flexion_23"][0]),
                    f"cote {side['cote']} : C9.7.5-52 doit etre en defaut hors "
                    "domaine ; un sigma_ball negatif pris en valeur absolue "
                    f"aurait autorise |sigma_bx| = {abs(bx):.1f} MPa")
        assert_vrai(not bool(adm["ok_global"][0]),
                    f"cote {side['cote']} : le verdict global doit etre non-OK")
        # 3) la situation est signalee, non silencieusement absorbee
        assert_vrai(bool(adm["hors_domaine_interaction"][0]),
                    f"cote {side['cote']} : hors_domaine_interaction doit etre leve")
        # 4) le taux d'utilisation ne doit pas etre fini et flatteur
        assert_vrai(not np.isfinite(float(np.asarray(adm["taux_max"], float)[0])),
                    f"cote {side['cote']} : le taux d'utilisation ne doit pas "
                    "etre fini lorsque sigma_ball est nul")

    syn = res["synthese"]
    assert_vrai(not bool(syn["TENUE"][0]),
                f"la synthese doit conclure a la non-tenue, obtenu "
                f"{syn['verdict'][0]!r}")
    assert_vrai(bool(syn["hors_domaine"][0]),
                "la synthese doit propager l'indicateur hors_domaine")


def test_garde_fou_section_1_est_surabondant():
    """
    C9.7.5-32 borne |v2| en section 1 : la reussite de -32 impose |v2| <= S*phi_S.

    Consequence : le garde-fou |v2| <= 1 ne peut jamais s'activer en section 1
    sans que C9.7.5-32 ait deja echoue. On le verifie sur le cas sature.
    """
    res = _res(_cas(p=20.0))
    S, phiS = CAS_REFERENCE["S"], CAS_REFERENCE["phiS"]
    for side in res["sides"]:
        adm = side["adm"]
        v2_1 = float(np.asarray(adm["v2_1"], float)[0])
        if bool(adm["ok_membrane_1"][0]):
            assert_vrai(abs(v2_1) <= S * phiS + 1e-12,
                        f"C9.7.5-32 satisfaite implique |v2_1| <= S*phi_S = "
                        f"{S * phiS:.4f}, obtenu {abs(v2_1):.4f}")
            assert_vrai(abs(v2_1) <= 1.0,
                        f"le garde-fou de la section 1 ne devrait pas s'activer "
                        f"quand C9.7.5-32 passe, obtenu |v2_1| = {abs(v2_1):.4f}")


if __name__ == "__main__":
    sys.exit(_runner.executer(dict(globals()),
                              "Chaine C9.7.5 -- cas de reference et invariants"))
