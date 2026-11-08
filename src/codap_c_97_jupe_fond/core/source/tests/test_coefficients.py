# coding: utf-8
"""
Validation des coefficients Cij -- CODAP 2015 Div.2, Annexe C9.A6.

Trois niveaux de controle, du plus structurel au plus factuel :

  1. STRUCTURE des tables numerisees (`_tables_C9A6.CIJ_TABLES`). Les tables
     sont un fichier genere ; on ne verifie donc pas leurs coefficients un par
     un, mais les INVARIANTS que toute numerisation correcte d'un faisceau
     d'abaques doit satisfaire : chainage des polynomes d'ancrage, symetrie des
     tranches extremes, et continuite de la fonction reconstruite. Une faute de
     transcription d'un ancrage casse necessairement l'un des trois.

  2. ASSEMBLAGE des 42 coefficients du raccordement type C
     (`assembly.compute_cij`) : completude, absence de NaN, formes closes de
     C9.A6.4-1 a -7 et identites de C9.A6.4-3 et -8 a -14.

  3. NON-REGRESSION contre le script historique
     `JupeFond_CODAP_C9-7_v2022.py`, qui constitue le temoin verifie page a
     page contre le texte reglementaire.
"""
from __future__ import annotations

import ast
import sys
import warnings
from math import log
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runner
from _runner import (INPUT_CODAP_REF, SCRIPT_HISTORIQUE, assert_proche,
                     assert_vrai, attend_exception)

from codap_c97.coefficients._tables_C9A6 import CIJ_TABLES
from codap_c97.coefficients.assembly import (COEF_ORDER, TABULATED_HEAD_DEPENDENT,
                                             TABULATED_PLAIN, compute_cij)
from codap_c97.coefficients.interp import evaluate_cij
from codap_c97.config import FOND_ELLIPTIQUE, FOND_KORBBOGEN
from codap_c97.io_excel import read_input_codap

#: Nombre d'entrees attendu dans CIJ_TABLES : 23 coefficients independants du
#: type de fond + 5 coefficients Ci1 pour chacun des deux types de fond.
N_ENTREES_ATTENDU = 33

#: Les 28 coefficients tabules du raccordement type C (5 famille A + 23 famille B)
COEF_TABULES = tuple(TABULATED_HEAD_DEPENDENT) + tuple(TABULATED_PLAIN)


# ==========================================================================
# 1. Structure des tables numerisees
# ==========================================================================
def _bandes(spec):
    """Retourne la liste des tranches sous la forme (borne_sup, z1, p1, z2, p2)."""
    return spec["bands"]


def test_tables_C9A6_nombre_d_entrees():
    """CIJ_TABLES : 33 entrees -- 23 coefficients + 5 Ci1 x 2 types de fond."""
    assert_vrai(len(CIJ_TABLES) == N_ENTREES_ATTENDU,
                f"CIJ_TABLES devrait comporter {N_ENTREES_ATTENDU} entrees, "
                f"{len(CIJ_TABLES)} trouvee(s) : {sorted(map(str, CIJ_TABLES))}")
    assert_vrai(len(COEF_TABULES) == 28,
                f"28 coefficients tabules attendus, {len(COEF_TABULES)} declares")
    # les 5 coefficients dependants du fond doivent l'etre pour les DEUX fonds
    for nom in TABULATED_HEAD_DEPENDENT:
        for fond in (FOND_ELLIPTIQUE, FOND_KORBBOGEN):
            assert_vrai((nom, fond) in CIJ_TABLES,
                        f"entree ({nom!r}, {fond!r}) absente de CIJ_TABLES")


def test_tables_C9A6_chainage_de_la_chaine_interieure():
    """C9.A6.5 : y2 de la tranche i = y1 de la tranche i+1 (chaine interieure)."""
    for cle, spec in CIJ_TABLES.items():
        b = _bandes(spec)
        n = len(b)
        assert_vrai(n >= 4, f"{cle} : {n} tranche(s), au moins 4 attendues "
                            "(2 extremes + chaine interieure)")
        # tranche 0 et tranche n-1 sont les tranches extremes ; la chaine
        # interieure va de la tranche 1 a la tranche n-2. On verifie donc le
        # raccord pour i de 1 a n-3 inclus.
        for i in range(1, n - 2):
            z2_i, p2_i = b[i][3], b[i][4]
            z1_j, p1_j = b[i + 1][1], b[i + 1][2]
            assert_vrai(
                z2_i == z1_j and tuple(p2_i) == tuple(p1_j),
                f"{cle} : rupture de chainage entre les tranches {i} et {i + 1}.\n"
                f"    tranche {i}   : z2 = {z2_i}, p2 = {p2_i}\n"
                f"    tranche {i + 1} : z1 = {z1_j}, p1 = {p1_j}")


def test_tables_C9A6_tranches_extremes_identiques():
    """C9.A6.5 : la tranche non bornee reprend les deux ancrages extremes."""
    for cle, spec in CIJ_TABLES.items():
        b = _bandes(spec)
        premiere, derniere = b[0], b[-1]
        assert_vrai(derniere[0] is None,
                    f"{cle} : la derniere tranche devrait etre non bornee "
                    f"(borne_sup = None), trouve {derniere[0]!r}")
        assert_vrai(
            premiere[1] == derniere[1] and tuple(premiere[2]) == tuple(derniere[2])
            and premiere[3] == derniere[3] and tuple(premiere[4]) == tuple(derniere[4]),
            f"{cle} : les tranches extremes devraient etre identiques "
            f"(hors borne superieure).\n"
            f"    premiere : z1={premiere[1]}, z2={premiere[3]}\n"
            f"    derniere : z1={derniere[1]}, z2={derniere[3]}")
        # les deux ancrages de la tranche extreme sont les ancrages extremes
        noeuds = sorted({z for tr in b for z in (tr[1], tr[3])})
        assert_vrai(premiere[1] == noeuds[0] and premiere[3] == noeuds[-1],
                    f"{cle} : la tranche extreme devrait s'appuyer sur les "
                    f"ancrages {noeuds[0]} et {noeuds[-1]}, trouve "
                    f"{premiere[1]} et {premiere[3]}")


def test_tables_C9A6_polynomes_distincts_egalent_noeuds_distincts():
    """C9.A6.5 : un polynome par noeud du faisceau -- pas de doublon ni d'orphelin."""
    for cle, spec in CIJ_TABLES.items():
        b = _bandes(spec)
        polynomes, noeuds, appariement = set(), set(), {}
        for _hi, z1, p1, z2, p2 in b:
            for z, p in ((z1, tuple(p1)), (z2, tuple(p2))):
                polynomes.add(p)
                noeuds.add(z)
                if z in appariement:
                    assert_vrai(appariement[z] == p,
                                f"{cle} : le noeud z = {z} est associe a deux "
                                f"polynomes differents {appariement[z]} et {p}")
                appariement[z] = p
        assert_vrai(len(polynomes) == len(noeuds),
                    f"{cle} : {len(polynomes)} polynome(s) distinct(s) pour "
                    f"{len(noeuds)} noeud(s) distinct(s) {sorted(noeuds)} -- "
                    "la numerisation doit associer exactement un polynome par noeud")


def test_tables_C9A6_continuite_de_la_fonction_reconstruite():
    """
    C9.A6.5 : la cascade de tranches reconstruit une fonction CONTINUE du pilote.

    C'est la consequence observable du chainage : de part et d'autre de chaque
    noeud, l'interpolation lineaire en z est ancree sur le meme polynome, donc
    la valeur ne saute pas. Une faute de transcription d'un ancrage produirait
    ici un saut fini.
    """
    eps = 1e-9
    pire, ou = 0.0, None
    for cle, spec in CIJ_TABLES.items():
        nom = cle if isinstance(cle, str) else cle[0]
        fond = None if isinstance(cle, str) else cle[1]
        noeuds = sorted({z for tr in spec["bands"] for z in (tr[1], tr[3])})
        # abscisses de balayage, dans le domaine tabule de chaque variable x
        if spec["xvar"] == "lambda1":
            x = np.array([30.0, 60.0, 123.0, 250.0, 400.0])
        else:
            x = np.array([0.5, 0.8, 1.0, 1.2, 1.3])
        for z in noeuds:
            zm = np.full(x.shape, z - eps)
            zp = np.full(x.shape, z + eps)
            if spec["driver"] == "delta1":
                un = np.ones_like(x)
                vm = evaluate_cij(nom, zm, un, x, head=fond)
                vp = evaluate_cij(nom, zp, un, x, head=fond)
            else:
                l1 = np.full(x.shape, 123.0)
                vm = evaluate_cij(nom, x, zm, l1, head=fond)
                vp = evaluate_cij(nom, x, zp, l1, head=fond)
            saut = np.max(np.abs(vm - vp) / np.maximum(np.abs(vm), 1e-3))
            if saut > pire:
                pire, ou = saut, (cle, z)
    assert_vrai(pire <= 1e-6,
                f"saut relatif de {pire:.3e} au franchissement d'un noeud "
                f"{ou} : la fonction reconstruite n'est pas continue")


# ==========================================================================
# 2. Assemblage des 42 coefficients (raccordement type C)
# ==========================================================================
def _grille_geometrique():
    """
    Grille de geometries balayant tout le domaine tabule de delta1 et lambda1,
    plus deux points d'extrapolation deliberee (delta1 = 0,45 et 1,50).
    """
    delta1 = np.array([0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5])
    lambda1 = np.array([25.0, 30.0, 60.0, 123.0, 250.0, 400.0, 500.0])
    d1, l1 = np.meshgrid(delta1, lambda1, indexing="ij")
    d1, l1 = d1.ravel(), l1.ravel()
    eu1 = np.full(d1.shape, 10.0)
    eu2 = np.full(d1.shape, 10.0)
    eu3 = d1 * eu1
    D1 = l1 * eu2
    return eu1, eu2, eu3, D1, d1, l1


def test_compute_cij_42_coefficients_sans_nan():
    """C9.7.5 etape 4 : les 42 Cij du type C sont fournis, finis, pour les 2 fonds."""
    eu1, eu2, eu3, D1, _d1, _l1 = _grille_geometrique()
    assert_vrai(len(COEF_ORDER) == 42,
                f"COEF_ORDER devrait compter 42 coefficients, {len(COEF_ORDER)} trouve(s)")
    assert_vrai(len(set(COEF_ORDER)) == 42, "COEF_ORDER comporte des doublons")
    for fond in (FOND_ELLIPTIQUE, FOND_KORBBOGEN):
        C = compute_cij(eu1, eu2, eu3, D1, head=fond)
        assert_vrai(set(C) == set(COEF_ORDER),
                    f"fond {fond} : coefficients manquants "
                    f"{sorted(set(COEF_ORDER) - set(C))} / en trop "
                    f"{sorted(set(C) - set(COEF_ORDER))}")
        assert_vrai(list(C) == list(COEF_ORDER),
                    f"fond {fond} : l'ordre de restitution differe de COEF_ORDER")
        for nom in COEF_ORDER:
            v = np.asarray(C[nom], float)
            assert_vrai(v.shape == eu1.shape,
                        f"fond {fond} : {nom} de forme {v.shape}, attendu {eu1.shape}")
            assert_vrai(np.all(np.isfinite(v)),
                        f"fond {fond} : {nom} comporte "
                        f"{int(np.count_nonzero(~np.isfinite(v)))} valeur(s) "
                        "non finie(s) (NaN ou inf)")


def test_formes_closes_C9A6_4():
    """C9.A6.4-1, -2, -4, -5, -6, -7 : les six coefficients d'equilibre."""
    eu1, eu2, eu3, D1, d1, _l1 = _grille_geometrique()
    for fond in (FOND_ELLIPTIQUE, FOND_KORBBOGEN):
        C = compute_cij(eu1, eu2, eu3, D1, head=fond)
        delta1 = np.asarray(C.delta1, float)
        delta2 = np.asarray(C.delta2, float)
        assert_proche(delta1, d1, rtol=1e-14, nom="delta1", ref="C9.7.5-16")
        # C9.7.5-17 : delta2 = 1,0 identiquement en raccordement type C
        assert_proche(delta2, np.ones_like(delta2), rtol=0.0, atol=0.0,
                      nom="delta2", ref="C9.7.5-17")
        assert_proche(C["C41"], 0.5 / delta2, rtol=1e-14, nom="C41", ref="C9.A6.4-1")
        assert_proche(C["C71"], np.full_like(delta1, 0.5), rtol=0.0, atol=0.0,
                      nom="C71", ref="C9.A6.4-2")
        assert_proche(C["C12"], -0.5 / delta1, rtol=1e-14, nom="C12", ref="C9.A6.4-4")
        assert_proche(C["C72"], np.full_like(delta1, -0.5), rtol=0.0, atol=0.0,
                      nom="C72", ref="C9.A6.4-5")
        assert_proche(C["C13"], -1.0 / delta1, rtol=1e-14, nom="C13", ref="C9.A6.4-6")
        assert_proche(C["C73"], np.full_like(delta1, -1.0), rtol=0.0, atol=0.0,
                      nom="C73", ref="C9.A6.4-7")


def test_identites_C9A6_4():
    """C9.A6.4-3 et -8 a -14 : les sept identites entre coefficients."""
    identites = [("C91", "C61", "C9.A6.4-3"),
                 ("C64", "C34", "C9.A6.4-8"),
                 ("C94", "C34", "C9.A6.4-9"),
                 ("C95", "C65", "C9.A6.4-10"),
                 ("C66", "C36", "C9.A6.4-11"),
                 ("C96", "C36", "C9.A6.4-12"),
                 ("C67", "C37", "C9.A6.4-13"),
                 ("C97", "C37", "C9.A6.4-14")]
    eu1, eu2, eu3, D1, _d1, _l1 = _grille_geometrique()
    for fond in (FOND_ELLIPTIQUE, FOND_KORBBOGEN):
        C = compute_cij(eu1, eu2, eu3, D1, head=fond)
        for gauche, droite, ref in identites:
            assert_vrai(
                np.array_equal(np.asarray(C[gauche]), np.asarray(C[droite])),
                f"fond {fond} : {ref} exige {gauche} = {droite} ; ecart maximal "
                f"{np.max(np.abs(np.asarray(C[gauche]) - np.asarray(C[droite]))):.3e}")


def test_evaluate_cij_exige_le_type_de_fond():
    """C9.A6.5.2.1 : C21 depend du fond ; l'omettre doit lever KeyError."""
    un = np.array([1.0])
    exc = attend_exception(KeyError, evaluate_cij, "C21", un, un, np.array([123.0]))
    msg = str(exc)
    assert_vrai("C21" in msg and "fond" in msg.lower(),
                f"le message d'erreur devrait nommer C21 et le type de fond : {msg}")
    # un coefficient inconnu doit egalement lever KeyError, avec un autre motif
    exc2 = attend_exception(KeyError, evaluate_cij, "C99", un, un, np.array([123.0]))
    assert_vrai("C99" in str(exc2), f"message inattendu : {exc2}")
    # avec le fond precise, l'evaluation doit aboutir
    v = evaluate_cij("C21", un, un, np.array([123.0]), head=FOND_ELLIPTIQUE)
    assert_vrai(np.all(np.isfinite(v)), "C21 non fini avec head='elliptique'")


def test_compute_cij_refuse_le_fond_GRC_et_le_raccordement_AB():
    """C9.7.2.1 : le fond GRC impose le type AB, non couvert ; refus explicite."""
    un = np.array([8.0])
    exc = attend_exception(ValueError, compute_cij, un, un, un, np.array([984.0]),
                           head="grc")
    assert_vrai("C9.7.2.1" in str(exc) or "GRC" in str(exc).upper(),
                f"le refus devrait citer C9.7.2.1 ou le fond GRC : {exc}")
    exc2 = attend_exception(NotImplementedError, compute_cij, un, un, un,
                            np.array([984.0]), head=FOND_ELLIPTIQUE,
                            raccordement="AB")
    assert_vrai("AB" in str(exc2), f"le refus devrait nommer le type AB : {exc2}")


# ==========================================================================
# 3. Non-regression contre le script historique
# ==========================================================================
def _charger_fonctions_historiques(delta1, delta2, lambda1):
    """
    Isole par AST les fonctions `get_*Cij` du script historique et les rend
    appelables.

    Le script `JupeFond_CODAP_C9-7_v2022.py` n'est PAS importable :
      - il execute son pipeline d'entrees/sorties au chargement du module ;
      - il utilise `pandas.DataFrame.append`, supprime en pandas 2.0.
    On extrait donc uniquement les definitions de fonctions utiles, et on les
    execute dans un espace de noms controle ou l'on injecte les grandeurs que
    le script attendait comme variables globales.

    Les pilotes sont injectes en TABLEAUX COLONNE de forme (n, 1) : les
    fonctions historiques bouclent sur `range(len(lambda1))`, indexent
    `delta1[i]` et terminent par `.reshape(delta1.shape)`. La forme (n, 1)
    reproduit donc exactement le regime d'appel d'origine.

    Retourne (espace_de_noms, {nom_de_fonction: nom_de_coefficient}).
    """
    assert_vrai(SCRIPT_HISTORIQUE.exists(),
                f"temoin de non-regression introuvable : {SCRIPT_HISTORIQUE}\n"
                "    le controle de non-regression ne peut pas etre effectue")
    source = SCRIPT_HISTORIQUE.read_text(encoding="utf-8", errors="replace")
    arbre = ast.parse(source)

    def log_scalaire(x):
        # numpy >= 2.4 refuse math.log sur un tableau de taille 1 (le script 2022
        # l'appelle ainsi) : on le ramene au scalaire, resultat identique.
        return log(float(np.asarray(x).reshape(-1)[0]))

    espace = {"np": np, "log": log_scalaire,
              "delta1": delta1, "delta2": delta2, "lambda1": lambda1}
    correspondance = {}
    for noeud in arbre.body:
        if not isinstance(noeud, ast.FunctionDef):
            continue
        if not noeud.name.startswith("get_"):
            continue
        coef = noeud.name.rsplit("_", 1)[-1]
        if len(coef) != 3 or coef[0] != "C" or not coef[1:].isdigit():
            continue  # get_data_set et autres utilitaires d'E/S
        code = compile(ast.Module(body=[noeud], type_ignores=[]),
                       filename=str(SCRIPT_HISTORIQUE), mode="exec")
        exec(code, espace)  # noqa: S102 - execution deliberee du temoin
        correspondance[noeud.name] = coef
    return espace, correspondance


def test_non_regression_contre_le_script_historique():
    """
    C9.A6.5 : les 28 Cij tabules du cas elliptique reproduisent le script 2022.

    Confrontation sur les 117 configurations de `input_CODAP.xlsx`, tolerance
    relative 1e-12. L'ecart residuel n'est que de reassociation des operations
    flottantes (schema de Horner vectorise contre somme litterale des monomes).
    """
    assert_vrai(INPUT_CODAP_REF.exists(),
                f"classeur de reference introuvable : {INPUT_CODAP_REF}")
    data, meta = read_input_codap(INPUT_CODAP_REF)
    n = meta["n"]
    assert_vrai(n == 117, f"117 configurations attendues dans "
                          f"{INPUT_CODAP_REF.name}, {n} lue(s)")

    # pilotes de C9.7.5-16 a -18, en tableaux colonne (n, 1)
    delta1 = (np.asarray(data["eu3"], float) / np.asarray(data["eu1"], float)).reshape(n, 1)
    delta2 = np.ones((n, 1))               # C9.7.5-17, raccordement type C
    lambda1 = (np.asarray(data["D1"], float) / np.asarray(data["eu2"], float)).reshape(n, 1)

    espace, correspondance = _charger_fonctions_historiques(delta1, delta2, lambda1)
    assert_vrai(len(correspondance) == 28,
                f"28 fonctions get_*Cij attendues dans le script historique, "
                f"{len(correspondance)} isolee(s) : {sorted(correspondance)}")
    assert_vrai(set(correspondance.values()) == set(COEF_TABULES),
                "les coefficients tabules du script historique ne coincident pas "
                "avec ceux de l'assemblage : "
                f"{sorted(set(correspondance.values()) ^ set(COEF_TABULES))}")

    pire, ou = 0.0, None
    with warnings.catch_warnings():
        # les fonctions historiques evaluent `if delta1[i] <= 0.6` sur un
        # tableau de taille 1 : numpy le tolere en le signalant.
        warnings.simplefilter("ignore")
        for fonction, coef in sorted(correspondance.items(), key=lambda t: t[1]):
            if coef == "C92":
                # ecart voulu : le script 2022 porte +0,039, deux calculs independants retiennent -0,039
                # pour delta2 = 1 (voir _tables_C9A6.py) ; verifie a part par le test dedie ci-dessous.
                continue
            espace[fonction]()
            temoin = np.asarray(espace[coef], float)
            fond = FOND_ELLIPTIQUE if "elliptique" in fonction else None
            obtenu = evaluate_cij(coef, delta1, delta2, lambda1, head=fond)
            assert_vrai(obtenu.shape == temoin.shape,
                        f"{coef} : forme {obtenu.shape} contre {temoin.shape} "
                        "pour le temoin historique")
            assert_proche(obtenu, temoin, rtol=1e-12, nom=coef,
                          ref="non-regression / script 2022")
            rel = float(np.max(np.abs(obtenu - temoin)
                               / np.maximum(np.abs(temoin), 1e-300)))
            if rel > pire:
                pire, ou = rel, coef
    print(f"           ecart relatif maximal sur les 28 coefficients x {n} "
          f"configurations : {pire:.2e} ({ou})")


if __name__ == "__main__":
    sys.exit(_runner.executer(dict(globals()),
                              "Coefficients Cij -- Annexe C9.A6"))


def test_C26_terme_cubique_positif_comme_imprime():
    """
    C9.A6.5.2.6-9 et -11 : +0,598 x^3 (la transcription 2022 portait -0,598).
    Controle par continuite en delta2 : C26(x=1) croit de facon monotone avec z, 0,828 a 0,880 a 0,933.
    """
    d1 = np.ones((1, 1)); lam = np.full((1, 1), 100.0)
    vals = [float(evaluate_cij("C26", d1, np.full((1, 1), z), lam)[0, 0]) for z in (1.0, 1.1, 1.2)]
    assert_proche(vals[1], 0.282 + 2.068 - 2.068 + 0.598, rtol=1e-12, nom="C26(z=1,1)", ref="C9.A6.5.2.6-9")
    assert_vrai(vals[0] < vals[1] < vals[2], f"C26 non monotone en delta2 : {vals}")


def test_C92_noeud_delta2_egal_1_conforme_aux_calculs_independants():
    """
    C9.A6.5.9.2 : pour delta2 = 1, C92 = -0,039 + 0,007 x - 0,012 x^2 (x = delta1), valeur retenue par un logiciel
    specialise (cas 2000-16 : C92 = -0,04588 a delta1 = 1,1029) et par une note de calcul independante.
    """
    d1 = np.full((1, 1), 15.0 / 13.6); lam = np.full((1, 1), 1968 / 13.6)
    v = float(evaluate_cij("C92", d1, np.ones((1, 1)), lam)[0, 0])
    x = 15.0 / 13.6
    assert_proche(v, -0.039 + 0.007 * x - 0.012 * x * x, rtol=1e-12, nom="C92", ref="C9.A6.5.9.2")
    assert_proche(v, -0.04588, rtol=1e-3, nom="C92", ref="calcul independant, cas 2000-16")
