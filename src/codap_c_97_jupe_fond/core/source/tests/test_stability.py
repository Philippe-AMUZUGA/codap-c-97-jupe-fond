# coding: utf-8
"""
Validation de C9.7.6 (stabilite de la jupe) et de l'Annexe C9.A7 (section
affaiblie par une ou plusieurs ouvertures).

Les formules de C9.A7.3 ont ete relues contre le texte reglementaire
(CODAP 2015 Div.2, Partie C, page 2082) au cours de la presente revue :

    C9.A7.3-1   delta = arcsin(d/D4)
    C9.A7.3-2   theta = pi - delta
    C9.A7.3-3   Psi1  = MIN[1,0 ; (theta/pi)*(1 + K)]
    C9.A7.3-4   Psi3  = 0,5 * (sin(theta)/theta + cos(theta)*K) / (1 + K)
    C9.A7.3-7   Psi23 = K/(1 + K)
    C9.A7.3-8   Psi24 = (1/(6*theta)) * (2*l_te/D4)^3 * (e_t/e4)
    C9.A7.3-9   Psi25 = (theta/pi) * (Psi21 + Psi22 + Psi23 + Psi24)
    C9.A7.3-10  Psi2  = MIN{1,0 ; 0,5*Psi25
                            / MAX[ |Psi3 + 0,5*(l_te/D4 - cos(theta))| ;
                                   |0,5 - Psi3| ]}
avec K = (1/theta)*(2*l_te/D4)*(e_t/e4).

La transcription du module `codap_c97.stability` est conforme a ce texte, y
compris l'ABSENCE de valeur absolue en C9.A7.3-4. Cette absence est precisement
l'objet du controle `test_ECART_signe_de_Psi3_...` ci-dessous.

Quatre familles de controles :
  1. concordance des deux voies de calcul de l'Annexe C9.A7 ;
  2. bornes et monotonie des coefficients d'affaiblissement ;
  3. aiguillage normatif de `check_stability` entre C9.7.6.1, C9.7.6.2 et les
     trois branches de C9.7.6.3 ;
  4. absence de verdict favorable par defaut lorsque F_cmax ou M_max manquent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runner
from _runner import assert_proche, assert_vrai, attend_exception

from codap_c97.stability import (INSTABLE, NON_EVALUE, SEUIL_PSI_SECONDAIRE,
                                SEUIL_X, STABLE, Opening, check_stability,
                                compute_psi, psi_composed_section_C9A7_4,
                                psi_single_opening_C9A7_3, section_properties,
                                verify_C9A7_consistency)

#: Jupe de reference : D4 = 2000 mm, e4 = 20 mm
D4_REF, E4_REF = 2000.0, 20.0

#: Charges de reference vis-a-vis de l'instabilite (Annexe C9.A4, hors perimetre)
FY_REF, FCMAX_REF, MMAX_REF = 1.0e6, 1.0e7, 5.0e9


# ==========================================================================
# 1. Concordance des deux voies de l'Annexe C9.A7
# ==========================================================================
def test_concordance_C9A7_3_et_C9A7_4_sur_Psi1_et_Psi3():
    """
    C9.A7.3-3 contre C9.A7.4-1, C9.A7.3-4 contre C9.A7.4-3.

    Le modele de section composee de `psi_composed_section_C9A7_4` a ete calibre
    pour reproduire l'Annexe C9.A7.3 dans le cas d'une ouverture unique -- c'est
    le placement du renfort AU BORD de l'ouverture qui fait apparaitre le
    facteur cos(theta) de C9.A7.3-4. La concordance de Psi1 et Psi3 est donc la
    verification numerique de cette calibration, et la condition de legitimite
    de la generalisation a plusieurs ouvertures.
    """
    ecarts = verify_C9A7_consistency(D4=D4_REF, e4=E4_REF)
    assert_vrai(len(ecarts) >= 6,
                f"au moins 6 cas de calibration attendus, {len(ecarts)} obtenu(s)")
    pire1 = pire3 = 0.0
    for e in ecarts:
        pire1 = max(pire1, e["psi1"][2])
        pire3 = max(pire3, e["psi3"][2])
        assert_vrai(e["psi1"][2] < 1e-4,
                    f"C9.A7.3-3 / C9.A7.4-1 : Psi1 diverge sur {e['cas']} -- "
                    f"voie C9.A7.3 = {e['psi1'][0]:.8f}, voie C9.A7.4 = "
                    f"{e['psi1'][1]:.8f}, ecart = {e['psi1'][2]:.3e}")
        assert_vrai(e["psi3"][2] < 1e-4,
                    f"C9.A7.3-4 / C9.A7.4-3 : Psi3 diverge sur {e['cas']} -- "
                    f"voie C9.A7.3 = {e['psi3'][0]:.8f}, voie C9.A7.4 = "
                    f"{e['psi3'][1]:.8f}, ecart = {e['psi3'][2]:.3e}")
    print(f"           ecart maximal : Psi1 {pire1:.2e}, Psi3 {pire3:.2e} "
          "(seuil 1e-4)")


def test_reserve_documentee_sur_Psi2():
    """
    C9.A7.3-10 contre C9.A7.4-2 : Psi2 ne concorde PAS, et c'est documente.

    La construction Psi21..Psi25 de C9.A7.3-10 ne se deduit pas de la definition
    usuelle W_e = I_G/c retenue par le calcul de section composee. Le controle
    verifie que l'ecart est bien present et QUANTIFIE -- il ne doit pas etre
    masque -- afin qu'une future modification qui le ferait disparaitre
    silencieusement soit detectee.
    """
    ecarts = verify_C9A7_consistency(D4=D4_REF, e4=E4_REF)
    pires = [e["psi2"][2] for e in ecarts]
    assert_vrai(max(pires) > 1e-2,
                "l'ecart sur Psi2 entre C9.A7.3-10 et C9.A7.4-2 est cense etre "
                f"significatif ; ecart maximal observe {max(pires):.3e}. Si "
                "l'ecart a disparu, la reserve du module doit etre revue.")
    print(f"           ecart Psi2 entre les deux voies : "
          f"{min(pires):.3f} a {max(pires):.3f} (reserve documentee)")


# ==========================================================================
# 2. Bornes et monotonie des coefficients d'affaiblissement
# ==========================================================================
def _grille_ouvertures_realistes():
    """
    Ouvertures conformes au schema de principe de la Figure C9.A7.2-1.

    Le renfort est borne a l'epaisseur de la jupe (e_t <= e4) et le diametre a
    0,05*D4 au minimum : c'est le domaine ou les deux voies de l'Annexe C9.A7
    concordent, cf. `test_ECART_signe_de_Psi3_pour_un_renfort_surabondant`.
    """
    for d in np.linspace(0.05 * D4_REF, 0.99 * D4_REF, 25):
        for e_t in (0.0, 0.5 * E4_REF, E4_REF):
            for l_t in (0.0, 50.0, 150.0, 400.0):
                yield Opening(d=float(d), e_t=float(e_t), l_t=float(l_t))


def test_bornes_Psi1_Psi2_Psi3_par_la_voie_C9A7_3():
    """C9.A7.3-3 et -10 : MIN explicite a 1,0 ; C9.A7.3-4 : Psi3 >= 0."""
    n = 0
    for op in _grille_ouvertures_realistes():
        psi = psi_single_opening_C9A7_3(op, D4_REF, E4_REF)
        n += 1
        assert_vrai(psi.psi1 <= 1.0,
                    f"C9.A7.3-3 : le MIN a 1,0 n'a pas ete applique -- "
                    f"d={op.d:.1f}, e_t={op.e_t:.1f}, l_t={op.l_t:.1f} "
                    f"-> Psi1 = {psi.psi1!r}")
        assert_vrai(psi.psi2 <= 1.0,
                    f"C9.A7.3-10 : le MIN a 1,0 n'a pas ete applique -- "
                    f"d={op.d:.1f}, e_t={op.e_t:.1f}, l_t={op.l_t:.1f} "
                    f"-> Psi2 = {psi.psi2!r}")
        assert_vrai(psi.psi1 > 0.0 and psi.psi2 > 0.0,
                    f"Psi1 et Psi2 sont des rapports de resistances, donc "
                    f"strictement positifs -- d={op.d:.1f} -> "
                    f"Psi1 = {psi.psi1!r}, Psi2 = {psi.psi2!r}")
        assert_vrai(psi.psi3 >= 0.0,
                    f"C9.A7.2 definit Psi3 comme le rapport de la DISTANCE y_G "
                    f"au diametre D4, donc Psi3 >= 0 -- d={op.d:.1f}, "
                    f"e_t={op.e_t:.1f}, l_t={op.l_t:.1f} -> Psi3 = {psi.psi3!r}")
        assert_vrai(psi.voie == "C9.A7.3" and not psi.complement_ingenierie,
                    "une ouverture unique conforme doit emprunter la voie C9.A7.3 "
                    "sans complement d'ingenierie")
    assert_vrai(n >= 200, f"grille trop pauvre : {n} configurations")


def test_bornes_par_la_voie_C9A7_4_plusieurs_ouvertures():
    """C9.A7.4-1 a -3 : Psi1, Psi2 > 0 et Psi3 >= 0 en section composee."""
    jeux = [
        [Opening(d=400.0, phi=0.0), Opening(d=300.0, phi=np.pi / 2)],
        [Opening(d=600.0, e_t=20.0, l_t=150.0), Opening(d=400.0, phi=np.pi)],
        [Opening(d=300.0, phi=0.0), Opening(d=300.0, phi=2 * np.pi / 3),
         Opening(d=300.0, phi=-2 * np.pi / 3)],
    ]
    for ops in jeux:
        psi = psi_composed_section_C9A7_4(ops, D4_REF, E4_REF)
        etiquette = [f"d={o.d:.0f}@{np.degrees(o.phi):.0f}deg" for o in ops]
        assert_vrai(0.0 < psi.psi1 <= 1.0,
                    f"C9.A7.4-1 : Psi1 = {psi.psi1!r} hors ]0 ; 1] pour {etiquette}")
        assert_vrai(psi.psi2 > 0.0,
                    f"C9.A7.4-2 : Psi2 = {psi.psi2!r} devrait etre > 0 "
                    f"pour {etiquette}")
        assert_vrai(psi.psi3 >= 0.0,
                    f"C9.A7.4-3 : Psi3 = |y_G|/D4 >= 0 par construction, "
                    f"obtenu {psi.psi3!r} pour {etiquette}")
        assert_vrai(psi.voie == "C9.A7.4" and psi.complement_ingenierie,
                    "la voie C9.A7.4 doit etre signalee comme complement "
                    "d'ingenierie (le CODAP n'y donne aucune formule)")
    # trois ouvertures a 120 degres : la section reste centree, y_G ~ 0
    psi = psi_composed_section_C9A7_4(jeux[2], D4_REF, E4_REF)
    assert_vrai(psi.psi3 < 1e-6,
                f"trois ouvertures identiques a 120 degres : la section demeure "
                f"centree, Psi3 devrait etre nul, obtenu {psi.psi3:.3e}")


def test_monotonie_de_Psi1_avec_le_diametre_d_ouverture():
    """C9.A7.3-3 : Psi1 est un rapport d'aires, donc decroissant avec d."""
    for e_t, l_t in ((0.0, 0.0), (10.0, 100.0), (20.0, 150.0)):
        diametres = np.linspace(0.05 * D4_REF, 0.99 * D4_REF, 30)
        psis = [psi_single_opening_C9A7_3(
            Opening(d=float(d), e_t=e_t, l_t=l_t), D4_REF, E4_REF).psi1
            for d in diametres]
        for i in range(len(psis) - 1):
            assert_vrai(psis[i + 1] < psis[i] + 1e-15,
                        f"C9.A7.3-3 : Psi1 doit decroitre avec d "
                        f"(e_t={e_t}, l_t={l_t}) ; "
                        f"d = {diametres[i]:.1f} -> {psis[i]:.6f} puis "
                        f"d = {diametres[i + 1]:.1f} -> {psis[i + 1]:.6f}")
        # decroissance effective, non triviale
        assert_vrai(psis[0] - psis[-1] > 0.05,
                    f"la variation de Psi1 sur la plage de d est trop faible "
                    f"({psis[0]:.4f} -> {psis[-1]:.4f}) pour que le controle "
                    "de monotonie ait du sens")
    # Psi3 croit avec d : l'excentrement augmente quand la matiere retiree croit
    psi3 = [psi_single_opening_C9A7_3(Opening(d=float(d)), D4_REF, E4_REF).psi3
            for d in np.linspace(0.05 * D4_REF, 0.99 * D4_REF, 20)]
    for i in range(len(psi3) - 1):
        assert_vrai(psi3[i + 1] > psi3[i] - 1e-15,
                    f"C9.A7.3-4 : Psi3 doit croitre avec d (ouverture non "
                    f"renforcee), {psi3[i]:.6f} puis {psi3[i + 1]:.6f}")


def test_ouverture_non_renforcee_l_te_nul_sans_division_par_zero():
    """C9.A7.2 (notations) : e_t = 0 ou l_t = 0 -> l_te = 0, sans division par zero."""
    for e_t, l_t in ((0.0, 0.0), (0.0, 250.0), (20.0, 0.0)):
        op = Opening(d=400.0, e_t=e_t, l_t=l_t)
        assert_vrai(op.l_te() == 0.0,
                    f"l_te devrait etre nul pour e_t={e_t}, l_t={l_t}, "
                    f"obtenu {op.l_te()!r}")
        psi = psi_single_opening_C9A7_3(op, D4_REF, E4_REF)
        for nom, v in (("Psi1", psi.psi1), ("Psi2", psi.psi2), ("Psi3", psi.psi3)):
            assert_vrai(np.isfinite(v),
                        f"{nom} non fini pour une ouverture non renforcee "
                        f"(e_t={e_t}, l_t={l_t}) : {v!r}")
        assert_proche(psi.detail["K"], 0.0, rtol=0.0, atol=0.0, nom="K",
                      ref="C9.A7.3-3 / -7 sans renfort")
        assert_proche(psi.detail["psi24"], 0.0, rtol=0.0, atol=0.0, nom="Psi24",
                      ref="C9.A7.3-8 sans renfort")
        # sans renfort, C9.A7.3-3 se reduit a theta/pi et -7 a zero
        assert_proche(psi.psi1, min(1.0, psi.detail["theta"] / np.pi), rtol=1e-14,
                      nom="Psi1 = theta/pi", ref="C9.A7.3-3 sans renfort")
        assert_proche(psi.psi3,
                      0.5 * np.sin(psi.detail["theta"]) / psi.detail["theta"],
                      rtol=1e-14, nom="Psi3", ref="C9.A7.3-4 sans renfort")
        # la voie C9.A7.4 doit aussi tenir : aucune aire de renfort
        props = section_properties([op], D4_REF, E4_REF)
        assert_proche(props["A_renforts"], 0.0, rtol=0.0, atol=0.0,
                      nom="aire de renfort", ref="C9.A7.4")
    # geometrie non physique : d > D4 doit etre refuse et non calcule
    attend_exception(ValueError, psi_single_opening_C9A7_3,
                     Opening(d=D4_REF * 1.01), D4_REF, E4_REF)
    attend_exception(ValueError, psi_single_opening_C9A7_3,
                     Opening(d=0.0), D4_REF, E4_REF)


# ==========================================================================
# 3. Aiguillage normatif de check_stability
# ==========================================================================
def test_aiguillage_zero_ouverture_C9_7_6_1():
    """C9.7.6.1-1 : sans ouverture, F_Y/F_cmax + |M_Y|/M_max <= 1."""
    for MY in (1.0e9, -1.0e9, 6.0e9):
        r = check_stability(FY_REF, MY, D4_REF, E4_REF, [], FCMAX_REF, MMAX_REF)
        assert_vrai(r.equation == "C9.7.6.1-1",
                    f"equation C9.7.6.1-1 attendue, obtenu {r.equation!r}")
        assert_vrai(r.n_ouvertures == 0 and r.psi is None,
                    "aucun coefficient d'affaiblissement ne doit etre calcule")
        attendu = FY_REF / FCMAX_REF + abs(MY) / MMAX_REF
        assert_proche(r.critere, attendu, rtol=1e-14, nom="critere",
                      ref="C9.7.6.1-1")
        assert_vrai(r.statut == (STABLE if attendu <= 1.0 else INSTABLE),
                    f"statut incoherent avec le critere {attendu:.4f} : "
                    f"{r.statut}")


def test_aiguillage_une_ouverture_C9_7_6_2():
    """C9.7.6.2-1 : une ouverture, criteres ponderes par Psi1, Psi2, Psi3."""
    op = Opening(d=500.0, e_t=20.0, l_t=100.0)
    r = check_stability(FY_REF, 1.0e9, D4_REF, E4_REF, [op], FCMAX_REF, MMAX_REF)
    assert_vrai(r.equation == "C9.7.6.2-1",
                f"equation C9.7.6.2-1 attendue, obtenu {r.equation!r}")
    assert_vrai(r.n_ouvertures == 1 and r.psi is not None,
                "les coefficients d'affaiblissement doivent etre restitues")
    assert_vrai(r.psi.voie == "C9.A7.3",
                f"une ouverture conforme releve de C9.A7.3, obtenu {r.psi.voie!r}")
    p = r.psi
    attendu = (FY_REF / (p.psi1 * FCMAX_REF)
               + (abs(1.0e9) + FY_REF * p.psi3 * D4_REF) / (p.psi2 * MMAX_REF))
    assert_proche(r.critere, attendu, rtol=1e-14, nom="critere", ref="C9.7.6.2-1")
    # une ouverture non conforme au schema impose la voie C9.A7.4
    r2 = check_stability(FY_REF, 1.0e9, D4_REF, E4_REF,
                         [Opening(d=500.0, schema_conforme=False)],
                         FCMAX_REF, MMAX_REF)
    assert_vrai(r2.psi.voie == "C9.A7.4" and r2.psi.complement_ingenierie,
                "C9.A7.1 : une ouverture non conforme au schema de la Figure "
                f"C9.A7.2-1 impose la voie C9.A7.4, obtenu {r2.psi.voie!r}")


def test_aiguillage_plusieurs_ouvertures_branche_a():
    """
    C9.7.6.3, branche a) : toutes les ouvertures secondaires ont Psi1 et Psi2 > 0,95.

    Trois issues selon le parametre intermediaire x calcule sur la seule
    ouverture principale :
        x <= 0,9        -> C9.7.6.3-1, STABLE sans examen de l'ensemble
        x > 1,0         -> C9.7.6.3-1, INSTABLE
        0,9 < x <= 1,0  -> C9.7.6.3-2, reprise avec toutes les ouvertures
    """
    # ouverture secondaire d = 300 mm : Psi1 = 0,977 et Psi2 = 1,0, donc > 0,95
    ops = [Opening(d=900.0, e_t=20.0, l_t=100.0),
           Opening(d=300.0, phi=np.pi / 2)]
    secondaire = compute_psi([ops[1]], D4_REF, E4_REF)
    assert_vrai(secondaire.psi1 > SEUIL_PSI_SECONDAIRE
                and secondaire.psi2 > SEUIL_PSI_SECONDAIRE,
                f"le jeu doit declencher la branche a) : Psi1 = "
                f"{secondaire.psi1:.4f}, Psi2 = {secondaire.psi2:.4f}, "
                f"seuil {SEUIL_PSI_SECONDAIRE}")

    attendus = [
        (1.0e8, "C9.7.6.3-1", STABLE, "x <= 0,9"),
        (4.0e9, "C9.7.6.3-2", None, "0,9 < x <= 1,0"),
        (6.0e9, "C9.7.6.3-1", INSTABLE, "x > 1,0"),
    ]
    for MY, equation, statut, libelle in attendus:
        r = check_stability(FY_REF, MY, D4_REF, E4_REF, ops, FCMAX_REF, MMAX_REF)
        assert_vrai(r.detail["branche"] == "a",
                    f"branche a) attendue pour M_Y = {MY:.1e}, obtenu "
                    f"{r.detail['branche']!r}")
        assert_vrai(r.equation == equation,
                    f"{libelle} (M_Y = {MY:.1e}, x = {r.x:.4f}) : equation "
                    f"{equation} attendue, obtenu {r.equation!r}")
        if statut is not None:
            assert_vrai(r.statut == statut,
                        f"{libelle} : statut {statut} attendu, obtenu {r.statut}")
        assert_vrai(r.x is not None, "le parametre intermediaire x doit etre trace")
    # coherence des seuils traces avec ceux du module
    r = check_stability(FY_REF, 1.0e8, D4_REF, E4_REF, ops, FCMAX_REF, MMAX_REF)
    assert_vrai(r.x <= SEUIL_X,
                f"x = {r.x:.4f} devrait etre <= {SEUIL_X} pour conclure "
                "directement par C9.7.6.3-1")


def test_aiguillage_plusieurs_ouvertures_branche_b():
    """C9.7.6.3, branche b) : un Psi secondaire <= 0,95 -> C9.7.6.3-3 direct."""
    # ouverture secondaire d = 700 mm : Psi1 = 0,918 <= 0,95
    ops = [Opening(d=900.0, e_t=20.0, l_t=100.0),
           Opening(d=700.0, phi=np.pi / 2)]
    secondaire = compute_psi([ops[1]], D4_REF, E4_REF)
    assert_vrai(secondaire.psi1 <= SEUIL_PSI_SECONDAIRE
                or secondaire.psi2 <= SEUIL_PSI_SECONDAIRE,
                f"le jeu doit declencher la branche b) : Psi1 = "
                f"{secondaire.psi1:.4f}, Psi2 = {secondaire.psi2:.4f}, "
                f"seuil {SEUIL_PSI_SECONDAIRE}")
    r = check_stability(FY_REF, 1.0e8, D4_REF, E4_REF, ops, FCMAX_REF, MMAX_REF)
    assert_vrai(r.detail["branche"] == "b",
                f"branche b) attendue, obtenu {r.detail['branche']!r}")
    assert_vrai(r.equation == "C9.7.6.3-3",
                f"equation C9.7.6.3-3 attendue, obtenu {r.equation!r}")
    assert_vrai(r.x is None,
                "la branche b) ne calcule pas de parametre intermediaire x, "
                f"obtenu x = {r.x!r}")
    assert_vrai(r.psi is not None and r.psi.voie == "C9.A7.4",
                "la branche b) considere toutes les ouvertures, donc la voie "
                f"C9.A7.4, obtenu {r.psi.voie if r.psi else None!r}")
    # l'ouverture d'indice 1 est bien celle de plus grand diametre equivalent
    ops_desordre = [Opening(d=700.0, phi=np.pi / 2),
                    Opening(d=900.0, e_t=20.0, l_t=100.0)]
    r2 = check_stability(FY_REF, 1.0e8, D4_REF, E4_REF, ops_desordre,
                         FCMAX_REF, MMAX_REF)
    assert_vrai(r2.detail["psi_secondaires"] == r.detail["psi_secondaires"],
                "C9.A7.2 : l'ouverture principale doit etre identifiee par son "
                "diametre, independamment de l'ordre de la sequence fournie")


# ==========================================================================
# 4. Donnee manquante : jamais de verdict favorable par defaut
# ==========================================================================
def test_Fcmax_ou_Mmax_absents_donnent_NON_EVALUE_jamais_STABLE():
    """
    C9.7.6 : F_cmax et M_max relevent de l'Annexe C9.A4, hors perimetre.

    Leur absence ne doit JAMAIS produire un verdict favorable : une donnee
    manquante n'est pas une verification reussie.
    """
    jeux_d_ouvertures = [
        [],
        [Opening(d=500.0)],
        [Opening(d=900.0, e_t=20.0, l_t=100.0), Opening(d=300.0, phi=np.pi / 2)],
    ]
    combinaisons = [(None, MMAX_REF), (FCMAX_REF, None), (None, None)]
    for ops in jeux_d_ouvertures:
        for Fcmax, Mmax in combinaisons:
            for MY in (0.0, 1.0e9, 1.0e12):
                r = check_stability(FY_REF, MY, D4_REF, E4_REF, ops,
                                    Fcmax=Fcmax, Mmax=Mmax)
                assert_vrai(r.statut == NON_EVALUE,
                            f"statut {NON_EVALUE!r} attendu pour "
                            f"Fcmax={Fcmax!r}, Mmax={Mmax!r}, "
                            f"{len(ops)} ouverture(s), obtenu {r.statut!r}")
                assert_vrai(r.statut != STABLE,
                            "une donnee manquante ne doit jamais produire "
                            "un verdict STABLE")
                assert_vrai(r.critere is None,
                            f"aucun critere ne peut etre calcule, obtenu "
                            f"{r.critere!r}")
                assert_vrai("C9.A4" in r.motif,
                            f"le motif doit renvoyer a l'Annexe C9.A4 : {r.motif!r}")
                assert_vrai(r.n_ouvertures == len(ops),
                            "le nombre d'ouvertures doit rester trace")
    # des valeurs non physiques doivent etre refusees, non ignorees
    attend_exception(ValueError, check_stability, FY_REF, 1.0e9, D4_REF, E4_REF,
                     [Opening(d=500.0)], 0.0, MMAX_REF)
    attend_exception(ValueError, check_stability, FY_REF, 1.0e9, D4_REF, E4_REF,
                     [Opening(d=500.0)], FCMAX_REF, -1.0)


# ==========================================================================
# 5. Ecart releve au cours de la revue -- signe de Psi3
# ==========================================================================
def test_valeur_absolue_de_Psi3_en_C9A7_3_4():
    """
    C9.A7.3-4 : la valeur absolue omise par le texte est retablie.

    L'equation C9.A7.3-4 s'ecrit, dans le texte (page 2082), SANS valeur absolue :

        Psi3 = 0,5 * (sin(theta)/theta + cos(theta)*K) / (1 + K)

    Comme theta = pi - delta > pi/2, cos(theta) est NEGATIF. Des que
    K*|cos(theta)| depasse sin(theta)/theta -- ce qui survient pour des renforts
    tout a fait courants, tel un piquage renforce par une plaque de doublement
    d'epaisseur double de celle de la jupe -- le numerateur devient negatif.

    Or Psi3 est defini comme le rapport d'une DISTANCE au diametre D4, en C9.7.3
    comme en C9.A7.2, et C9.A7.4-3 l'ecrit explicitement |y_G|/D4, valeur absolue
    comprise. C9.A7.3-4 omet donc une valeur absolue que la voie parallele de la
    meme annexe porte.

    L'enjeu est la securite : dans C9.7.6.2-1, le terme + F_Y*Psi3*D4 MAJORE le
    moment sollicitant pour representer le moment parasite d'excentrement. Un Psi3
    negatif le RETRANCHE, rendant le critere non conservatif.

    Le module retient donc la valeur absolue, et conserve la valeur signee du
    texte litteral dans `detail['psi3_litteral']`, avec l'indicateur
    `detail['psi3_signe_inverse']`. Ce test verifie les trois proprietes :
    positivite, tracabilite de la valeur litterale, et concordance de signe entre
    les deux voies de l'annexe.
    """
    cas = [(60.0, E4_REF, 100.0),          # petite ouverture, renfort e_t = e4
           (200.0, 2 * E4_REF, 200.0),     # renfort e_t = 2*e4
           (400.0, 2 * E4_REF, 200.0),
           (600.0, 0.0, 0.0),              # sans renfort : le signe est deja bon
           (900.0, 0.0, 0.0)]
    n_inverses = 0
    for d, e_t, l_t in cas:
        op = Opening(d=d, e_t=e_t, l_t=l_t)
        a = psi_single_opening_C9A7_3(op, D4_REF, E4_REF)
        b = psi_composed_section_C9A7_4([op], D4_REF, E4_REF)

        # 1. positivite, conformement a la definition de Psi3
        assert_vrai(a.psi3 >= 0.0,
                    f"Psi3 doit etre positif (rapport d'une distance a D4) ; "
                    f"obtenu {a.psi3!r} pour d={d}, e_t={e_t}, l_t={l_t}")

        # 2. tracabilite : la valeur litterale du texte est conservee
        litt = a.detail["psi3_litteral"]
        inverse = a.detail["psi3_signe_inverse"]
        assert_proche(abs(litt), a.psi3, rtol=1e-12, atol=0.0,
                      nom="|psi3_litteral| contre psi3 retenu",
                      ref="C9.A7.3-4")
        assert_vrai(inverse == (litt < 0.0),
                    "l'indicateur psi3_signe_inverse doit refleter le signe de la "
                    f"valeur litterale ; litteral={litt!r}, indicateur={inverse!r}")
        n_inverses += int(inverse)

        # 3. les deux voies concordent desormais en signe ET en module. La
        # tolerance absolue de 1e-6 couvre la discretisation du masque angulaire
        # de `section_properties` (pas de 3,1e-5 rad), dont l'effet relatif
        # devient sensible pour les petites ouvertures.
        assert_proche(a.psi3, b.psi3, rtol=1e-3, atol=1e-6,
                      nom="Psi3 des deux voies",
                      ref="C9.A7.3-4 contre C9.A7.4-3")

        # quantification de la non-conservativite evitee
        FY, MY = 2.0e6, 1.0e9
        retenu = (FY / (a.psi1 * FCMAX_REF)
                  + (abs(MY) + FY * a.psi3 * D4_REF) / (a.psi2 * MMAX_REF))
        litteral = (FY / (a.psi1 * FCMAX_REF)
                    + (abs(MY) + FY * litt * D4_REF) / (a.psi2 * MMAX_REF))
        ecart = 100.0 * (retenu - litteral) / retenu
        print(f"           d={d:6.1f} e_t={e_t:5.1f} : litteral {litt:+.6f} -> "
              f"retenu {a.psi3:+.6f}"
              + (f" ; C9.7.6.2-1 aurait ete sous-estime de {ecart:.2f} %"
                 if inverse else " ; signe deja correct"))

    assert_vrai(n_inverses >= 3,
                "le jeu de cas doit comporter au moins trois configurations ou le "
                f"texte litteral rend Psi3 < 0 ; obtenu {n_inverses}")


if __name__ == "__main__":
    sys.exit(_runner.executer(dict(globals()),
                              "Stabilite de la jupe -- C9.7.6 et Annexe C9.A7"))
