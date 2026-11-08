# coding: utf-8
"""
Validation des entrees/sorties et de la chaine complete.

  1. LECTURE de #INPUT_CODAP : les 35 grandeurs reglementaires, les 117
     configurations du classeur de reference, et le refus explicite d'un
     classeur incomplet.

  2. CHAINE COMPLETE lecture -> `run_c975` -> ecriture de #OUTPUT_CODAP :
     structure du classeur produit, en particulier la feuille de synthese.

  3. NON-CONFORMITE REGLEMENTAIRE du pretraitement. C'est le controle le plus
     important de ce fichier : `input_EF.xlsx` decrit une geometrie de fond
     torispherique GRC (R1 = D1 et R2 = 0,10*D1, signature NF E 81-102). Or
     C9.7.2.1 impose le raccordement de type AB pour un fond GRC. La conversion
     vers un jeu de donnees type C doit donc etre REFUSEE, et non produire
     silencieusement un classeur exploitable -- l'Annexe C9.A6 ne fournissant
     d'ailleurs aucun coefficient Ci1 pour le couple (GRC ; type C).
"""
from __future__ import annotations

import gc
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runner
from _runner import (INPUT_CODAP_REF, INPUT_EF_REF, assert_proche, assert_vrai,
                     attend_exception)

from codap_c97.config import (RACCORD_C, SHEET_INPUT_CODAP, SHEET_OUT_COEF,
                              SHEET_OUT_MAIN, SHEET_OUT_SYNTH)
from codap_c97.io_excel import (INPUT_COLUMNS, OPTIONAL_COLUMNS,
                                read_input_codap, write_output_codap)
from codap_c97.runner import run_c975

from Preprocess import classify_head, convert_ef_to_codap

#: Nombre de configurations du classeur de reference
N_CONFIGURATIONS = 117
#: Nombre de grandeurs reglementaires obligatoires
N_COLONNES_OBLIGATOIRES = 35


# ==========================================================================
# 1. Lecture de #INPUT_CODAP
# ==========================================================================
def test_read_input_codap_117_lignes_et_35_colonnes():
    """Lecture de #INPUT_CODAP : 117 configurations, 35 grandeurs obligatoires."""
    assert_vrai(INPUT_CODAP_REF.exists(),
                f"classeur de reference introuvable : {INPUT_CODAP_REF}")
    assert_vrai(len(INPUT_COLUMNS) == N_COLONNES_OBLIGATOIRES,
                f"INPUT_COLUMNS devrait declarer {N_COLONNES_OBLIGATOIRES} "
                f"grandeurs, {len(INPUT_COLUMNS)} trouvee(s)")

    data, meta = read_input_codap(INPUT_CODAP_REF)
    assert_vrai(meta["n"] == N_CONFIGURATIONS,
                f"{N_CONFIGURATIONS} lignes attendues, {meta['n']} lue(s)")
    assert_vrai(meta["sheet"] == SHEET_INPUT_CODAP,
                f"feuille {SHEET_INPUT_CODAP!r} attendue, {meta['sheet']!r} lue")

    manquantes = [c for c in INPUT_COLUMNS if c not in data]
    assert_vrai(not manquantes,
                f"colonnes obligatoires absentes du resultat de lecture : "
                f"{manquantes}")
    for nom in INPUT_COLUMNS:
        col = data[nom]
        assert_vrai(col.shape == (N_CONFIGURATIONS,),
                    f"colonne {nom} de forme {col.shape}, attendu "
                    f"({N_CONFIGURATIONS},)")
        assert_vrai(col.dtype == float,
                    f"colonne {nom} de type {col.dtype}, flottant attendu")
        assert_vrai(np.all(np.isfinite(col)),
                    f"colonne {nom} : "
                    f"{int(np.count_nonzero(~np.isfinite(col)))} valeur(s) "
                    "manquante(s) ou non finie(s)")
    # aucune colonne parasite : seules les colonnes declarees sont restituees
    inattendues = [c for c in data
                   if c not in INPUT_COLUMNS and c not in OPTIONAL_COLUMNS]
    assert_vrai(not inattendues,
                f"colonnes non declarees restituees par la lecture : {inattendues}")
    # les epaisseurs et diametres doivent etre strictement positifs
    for nom in ("a1", "D1", "D3", "D4", "eu1", "eu2", "eu3", "f", "fj", "S", "E"):
        assert_vrai(np.all(data[nom] > 0),
                    f"colonne {nom} : valeur(s) non strictement positive(s) "
                    f"(minimum {data[nom].min()})")


def test_read_input_codap_colonne_obligatoire_manquante():
    """
    Lecture de #INPUT_CODAP : une grandeur obligatoire absente -> KeyError.

    NOTE DE REVUE -- fuite de descripteur sur les chemins d'erreur.
    `read_input_codap` ouvre le classeur par `openpyxl.load_workbook(...)` puis
    n'appelle `wb.close()` qu'en fin de traitement nominal. Sur ses trois
    chemins d'erreur (feuille absente, colonnes obligatoires absentes, feuille
    sans donnees), le classeur reste donc OUVERT. Sous Windows, le fichier
    d'entree demeure verrouille jusqu'a la finalisation de l'objet par le
    ramasse-miettes, ce qui empeche de le renommer, de le supprimer ou de le
    reecrire dans la meme execution -- situation courante d'une campagne qui
    corrige son classeur d'entree puis le relit.

    Ce test appelle donc explicitement `gc.collect()` avant le nettoyage de son
    repertoire temporaire ; sans cet appel, le repertoire ne peut pas etre
    supprime, ce qui est la manifestation directe de la fuite.
    """
    rep = Path(tempfile.mkdtemp(prefix="codap_qa_"))
    try:
        for supprimee in ("phiS", "eu3", "FZ"):
            chemin = rep / f"sans_{supprimee}.xlsx"
            _ecrire_classeur_incomplet(chemin, supprimee)
            exc = attend_exception(KeyError, read_input_codap, chemin)
            message = str(exc)
            assert_vrai(supprimee in message,
                        f"le message d'erreur devrait nommer la colonne "
                        f"{supprimee!r} : {message}")
            assert_vrai("obligatoire" in message.lower(),
                        f"le message d'erreur devrait qualifier la colonne "
                        f"d'obligatoire : {message}")
            assert_vrai(chemin.name in message,
                        f"le message d'erreur devrait nommer le classeur fautif "
                        f"({chemin.name}) : {message}")
        # classeur inexistant -> FileNotFoundError, et non KeyError
        attend_exception(FileNotFoundError, read_input_codap,
                         rep / "inexistant.xlsx")
        # classeur sans aucune ligne de donnees -> ValueError explicite
        vide = rep / "entetes_seules.xlsx"
        _ecrire_classeur_incomplet(vide, None, sans_donnees=True)
        exc = attend_exception(ValueError, read_input_codap, vide)
        assert_vrai("aucune ligne" in str(exc).lower(),
                    f"message inattendu pour un classeur sans donnees : {exc}")
    finally:
        # libere les classeurs restes ouverts sur les chemins d'erreur de
        # read_input_codap (cf. NOTE DE REVUE dans la docstring)
        del exc
        gc.collect()
        shutil.rmtree(rep, ignore_errors=True)
        assert_vrai(not rep.exists(),
                    f"repertoire temporaire non supprime : {rep}. Un descripteur "
                    "de fichier est reste ouvert par read_input_codap sur un "
                    "chemin d'erreur.")


def _ecrire_classeur_incomplet(chemin, colonne_supprimee, sans_donnees=False):
    """Recopie le classeur de reference en omettant une colonne obligatoire."""
    data, meta = read_input_codap(INPUT_CODAP_REF)
    noms = [c for c in INPUT_COLUMNS if c != colonne_supprimee]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_INPUT_CODAP
    for j, nom in enumerate(noms, start=1):
        ws.cell(1, j, nom)
    if not sans_donnees:
        for i in range(min(5, meta["n"])):
            for j, nom in enumerate(noms, start=1):
                ws.cell(i + 2, j, float(data[nom][i]))
    wb.save(chemin)
    return chemin


# ==========================================================================
# 2. Chaine complete : lecture -> calcul -> ecriture
# ==========================================================================
def test_pipeline_complet_et_structure_du_classeur_de_sortie():
    """Chaine C9.7.5 complete : 3 feuilles produites, 117 lignes de synthese."""
    data, meta = read_input_codap(INPUT_CODAP_REF)
    resultats = run_c975(data, verbose=False)

    # la configuration doit avoir ete resolue conformement au type C
    cfg = resultats["config"]
    assert_vrai(cfg["raccordement"] == RACCORD_C,
                f"raccordement {RACCORD_C!r} attendu, obtenu {cfg['raccordement']!r}")
    assert_vrai(cfg["n"] == N_CONFIGURATIONS,
                f"{N_CONFIGURATIONS} configurations attendues, obtenu {cfg['n']}")
    assert_vrai(len(resultats["sides"]) == 2,
                "les deux cotes du moment global doivent etre evalues "
                "(preambule de C9.7.5)")

    rep = Path(tempfile.mkdtemp(prefix="codap_qa_"))
    try:
        sortie = rep / "output_CODAP.xlsx"
        rendu = write_output_codap(sortie, data, resultats, meta)
        assert_vrai(Path(rendu).exists(), f"classeur de sortie non ecrit : {rendu}")

        wb = openpyxl.load_workbook(sortie, read_only=True, data_only=True)
        try:
            attendues = [SHEET_OUT_MAIN, SHEET_OUT_COEF, SHEET_OUT_SYNTH]
            assert_vrai(wb.sheetnames == attendues,
                        f"feuilles {attendues} attendues, obtenu {wb.sheetnames}")
            for feuille in attendues:
                ws = wb[feuille]
                lignes = list(ws.iter_rows(values_only=True))
                entete = [c for c in lignes[0] if c is not None]
                corps = [r for r in lignes[1:] if any(v is not None for v in r)]
                assert_vrai(len(corps) == N_CONFIGURATIONS,
                            f"feuille {feuille!r} : {N_CONFIGURATIONS} lignes de "
                            f"donnees attendues, {len(corps)} trouvee(s)")
                assert_vrai(len(entete) >= 3,
                            f"feuille {feuille!r} : en-tete trop pauvre {entete}")
            # la feuille de coefficients doit porter les 42 Cij et les 3 pilotes
            entete_coef = [c for c in next(
                wb[SHEET_OUT_COEF].iter_rows(values_only=True)) if c is not None]
            for nom in ("delta1", "delta2", "lambda1"):
                assert_vrai(nom in entete_coef,
                            f"feuille {SHEET_OUT_COEF!r} : colonne {nom!r} absente")
            n_cij = sum(1 for c in entete_coef
                        if len(str(c)) == 3 and str(c).startswith("C"))
            assert_vrai(n_cij == 42,
                        f"feuille {SHEET_OUT_COEF!r} : 42 coefficients attendus, "
                        f"{n_cij} trouve(s)")
            # la synthese doit porter le verdict et le taux d'utilisation
            entete_syn = [c for c in next(
                wb[SHEET_OUT_SYNTH].iter_rows(values_only=True)) if c is not None]
            for nom in ("TENUE", "verdict", "taux_utilisation_max",
                        "cote_determinant", "critere_determinant",
                        "dans_domaine_C9A6", "hors_domaine"):
                assert_vrai(nom in entete_syn,
                            f"feuille {SHEET_OUT_SYNTH!r} : colonne {nom!r} absente "
                            f"; colonnes presentes : {entete_syn}")
        finally:
            wb.close()

        # coherence interne de la synthese, cote calcul
        syn = resultats["synthese"]
        for nom, col in syn.items():
            assert_vrai(len(col) == N_CONFIGURATIONS,
                        f"synthese : colonne {nom!r} de longueur {len(col)}, "
                        f"attendu {N_CONFIGURATIONS}")
        ok_par_cote = [s["adm"]["ok_global"] for s in resultats["sides"]]
        attendu = ok_par_cote[0] & ok_par_cote[1]
        assert_vrai(np.array_equal(np.asarray(syn["TENUE"], bool),
                                   np.asarray(attendu, bool)),
                    "la TENUE enveloppe doit etre la conjonction des deux cotes")
        taux = np.asarray(syn["taux_utilisation_max"], float)
        pire = np.maximum(np.asarray(resultats["sides"][0]["adm"]["taux_max"], float),
                          np.asarray(resultats["sides"][1]["adm"]["taux_max"], float))
        assert_proche(taux, pire, rtol=1e-14,
                      nom="taux_utilisation_max", ref="enveloppe des deux cotes")
        # Caracterisation du jeu de reference : une part importante des
        # configurations sature la membrane des sections 2/3 (|v2| > 1), ce qui
        # rend sigma_ball nul et donc le taux d'utilisation infini. Ces cas
        # doivent etre signales hors domaine ET conclure a la non-tenue.
        infini = ~np.isfinite(taux)
        hors = np.asarray(syn["hors_domaine"], bool)
        assert_vrai(np.array_equal(infini, infini & hors),
                    "toute configuration a taux infini doit etre signalee hors "
                    "domaine d'interaction (C9.7.5-49 a -52)")
        assert_vrai(not np.any(np.asarray(syn["TENUE"], bool) & hors),
                    "aucune configuration hors domaine d'interaction ne doit "
                    "etre declaree en TENUE")
        print(f"           jeu de reference : "
              f"{int(np.count_nonzero(syn['TENUE']))}/{N_CONFIGURATIONS} en "
              f"TENUE, {int(np.count_nonzero(hors))} hors domaine "
              f"d'interaction |v2| <= 1, "
              f"{int(np.count_nonzero(~np.asarray(syn['dans_domaine_C9A6'], bool)))} "
              "hors domaine tabule C9.A6")
    finally:
        gc.collect()
        shutil.rmtree(rep, ignore_errors=True)
        assert_vrai(not rep.exists(),
                    f"repertoire temporaire non supprime : {rep} "
                    "(descripteur de fichier reste ouvert)")


# ==========================================================================
# 3. Non-conformite reglementaire du pretraitement
# ==========================================================================
def test_classify_head_identifie_la_geometrie_GRC():
    """C9.7.2.1 / NF E 81-102 : R1 = D et R2 = 0,10*D -> fond torispherique GRC."""
    D = np.array([700.0, 1200.0, 2000.0])
    types, detail = classify_head(D, 0.10 * D, D)
    assert_vrai(list(types) == ["grc"] * 3,
                f"signature GRC (R1/D = 1,00 ; R2/D = 0,10) attendue, "
                f"obtenu {list(types)}")
    assert_proche(detail["R1_sur_D"], np.ones(3), rtol=1e-14, nom="R1/D")
    assert_proche(detail["R2_sur_D"], np.full(3, 0.10), rtol=1e-14, nom="R2/D")
    # DIN 28013 : Korbbogen, R1 = 0,80*D et R2 = 0,154*D
    types_k, _ = classify_head(0.80 * D, 0.154 * D, D)
    assert_vrai(list(types_k) == ["korbbogen"] * 3,
                f"signature Korbbogen attendue, obtenu {list(types_k)}")
    # geometrie ne correspondant a aucune signature
    types_i, _ = classify_head(0.5 * D, 0.5 * D, D)
    assert_vrai(list(types_i) == ["indetermine"] * 3,
                f"classement 'indetermine' attendu, obtenu {list(types_i)}")

    # la geometrie effectivement portee par le classeur EF de reference
    assert_vrai(INPUT_EF_REF.exists(),
                f"classeur EF de reference introuvable : {INPUT_EF_REF}")
    R1, R2, D1 = _lire_rayons_EF(INPUT_EF_REF)
    types_ef, detail_ef = classify_head(R1, R2, D1)
    uniques = sorted(set(types_ef.astype(str)))
    assert_vrai(uniques == ["grc"],
                f"les {len(types_ef)} lignes de {INPUT_EF_REF.name} devraient "
                f"toutes etre classees 'grc', obtenu {uniques}")
    print(f"           {INPUT_EF_REF.name} : {len(types_ef)} geometries, "
          f"R1/D1 = {detail_ef['plages']['R1/D'][0]:.3f} a "
          f"{detail_ef['plages']['R1/D'][1]:.3f}, "
          f"R2/D1 = {detail_ef['plages']['R2/D'][0]:.3f} a "
          f"{detail_ef['plages']['R2/D'][1]:.3f} -> GRC")


def _lire_rayons_EF(chemin):
    """Extrait R1, R2 et D1 du classeur de geometrie EF."""
    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        lignes = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    entete = [(str(h).strip() if h is not None else None) for h in lignes[0]]
    idx = {h: j for j, h in enumerate(entete) if h}
    corps = [r for r in lignes[1:] if any(v is not None for v in r)]
    tire = lambda nom: np.array([float(r[idx[nom]]) for r in corps])  # noqa: E731
    return tire("R1"), tire("R2"), tire("D1")


def test_preprocess_refuse_un_fond_GRC_en_raccordement_type_C():
    """
    C9.7.2.1 : "fond torispherique GRC -> le raccordement doit etre de type AB".

    La conversion de `input_EF.xlsx` (geometrie GRC) vers un jeu de donnees de
    raccordement type C doit lever ValueError en citant C9.7.2.1. Produire
    silencieusement le classeur serait la faute la plus grave possible ici :
    l'Annexe C9.A6 ne fournit aucun coefficient Ci1 pour le couple
    (GRC ; type C), et tous les resultats aval seraient sans valeur.
    """
    assert_vrai(INPUT_EF_REF.exists(),
                f"classeur EF de reference introuvable : {INPUT_EF_REF}")
    rep = Path(tempfile.mkdtemp(prefix="codap_qa_"))
    try:
        destination = rep / "input_CODAP_depuis_EF.xlsx"
        exc = attend_exception(ValueError, convert_ef_to_codap,
                               INPUT_EF_REF, destination,
                               raccordement=RACCORD_C, verbose=False)
        message = str(exc)
        assert_vrai("C9.7.2.1" in message,
                    f"le refus doit citer C9.7.2.1 : {message}")
        assert_vrai("GRC" in message.upper(),
                    f"le refus doit nommer le fond GRC : {message}")
        assert_vrai("AB" in message,
                    f"le refus doit indiquer que le type AB est impose : {message}")
        assert_vrai(not destination.exists(),
                    "aucun classeur ne doit etre produit lorsque la conversion "
                    "est refusee")
    finally:
        gc.collect()
        shutil.rmtree(rep, ignore_errors=True)
        assert_vrai(not rep.exists(),
                    f"repertoire temporaire non supprime : {rep} "
                    "(descripteur de fichier reste ouvert)")


def test_preprocess_conversion_forcee_et_tracabilite():
    """
    C9.7.2.1 : le refus est levable explicitement, mais doit rester trace.

    `autoriser_fond_incompatible=True` permet l'etude comparative ; le classeur
    produit doit alors porter la feuille d'hypotheses et l'avertissement
    correspondant, le resultat n'ayant aucune valeur reglementaire.
    """
    rep = Path(tempfile.mkdtemp(prefix="codap_qa_"))
    try:
        destination = rep / "input_CODAP_force.xlsx"
        rendu = convert_ef_to_codap(INPUT_EF_REF, destination,
                                    raccordement=RACCORD_C,
                                    autoriser_fond_incompatible=True,
                                    verbose=False)
        assert_vrai(Path(rendu).exists(),
                    f"la conversion forcee doit produire le classeur : {rendu}")

        wb = openpyxl.load_workbook(destination, read_only=True, data_only=True)
        try:
            assert_vrai(SHEET_INPUT_CODAP in wb.sheetnames,
                        f"feuille {SHEET_INPUT_CODAP!r} attendue, obtenu "
                        f"{wb.sheetnames}")
            assert_vrai("hypotheses" in wb.sheetnames,
                        "la feuille de tracabilite des hypotheses est "
                        f"obligatoire, obtenu {wb.sheetnames}")
            texte = "\n".join(
                str(v) for ligne in wb["hypotheses"].iter_rows(values_only=True)
                for v in ligne if v is not None)
            assert_vrai("AVERTISSEMENT" in texte,
                        "la feuille d'hypotheses doit porter l'avertissement "
                        "sur l'incompatibilite C9.7.2.1")
            assert_vrai("C9.7.2.1" in texte,
                        f"la tracabilite doit citer C9.7.2.1 :\n{texte[:400]}")
        finally:
            wb.close()

        # le classeur produit doit etre relisible et complet
        data, meta = read_input_codap(destination)
        manquantes = [c for c in INPUT_COLUMNS if c not in data]
        assert_vrai(not manquantes,
                    f"le classeur converti doit porter les 35 grandeurs "
                    f"obligatoires ; absentes : {manquantes}")
        assert_vrai(meta["n"] > 0, "le classeur converti est vide")
        # type C : les conventions geometriques de C9.7.5-17 doivent etre tenues
        assert_proche(data["eu2"], data["eu1"], rtol=0.0, atol=0.0,
                      nom="eu2 = eu1", ref="C9.7.5-17 (delta2 = 1,0)")
        assert_proche(data["h4"], np.zeros(meta["n"]), rtol=0.0, atol=0.0,
                      nom="h4", ref="type C : pas d'emboitement")
        assert_proche(data["c"], np.zeros(meta["n"]), rtol=0.0, atol=0.0,
                      nom="c", ref="type C : fibres moyennes alignees")
        assert_proche(data["D4"], data["D3"], rtol=0.0, atol=0.0,
                      nom="D4 = D3", ref="type C : continuite de diametre")
    finally:
        gc.collect()
        shutil.rmtree(rep, ignore_errors=True)
        assert_vrai(not rep.exists(),
                    f"repertoire temporaire non supprime : {rep} "
                    "(descripteur de fichier reste ouvert)")


def test_casse_des_colonnes_de_configuration():
    """
    Normalisation de casse des colonnes de configuration -- non-regression.

    DEFAUT CORRIGE. La lecture normalisait uniformement en MINUSCULES les trois
    colonnes de configuration. Or les constantes du code n'ont pas la meme casse
    selon la grandeur : `type_raccordement` vaut 'AB' ou 'C' (majuscules,
    notation du CODAP), tandis que `type_fond` et `situation` valent
    'elliptique', 'korbbogen', 'autre', 'essai' (minuscules).

    La valeur 'C' devenait donc 'c', qui ne correspondait plus a RACCORD_C. La
    consequence la plus grave n'etait pas le refus de calcul, mais le fait que
    `check_application_conditions` cessait SILENCIEUSEMENT de verifier les trois
    conditions propres au type C -- delta2 = 1 (C9.7.5-17), h4 = 0 et D3 = D4 --
    et que le compte rendu n'en portait plus trace. Une verification incomplete
    pouvait ainsi passer pour complete.

    Ce test controle que la casse est normalisee par colonne, que les valeurs
    ecrites par `Preprocess.py` sont relues correctement, et qu'une valeur non
    reconnue echoue au lieu d'etre absorbee.
    """
    from codap_c97.io_excel import NORMALISATION_TEXTE
    from codap_c97.validation import check_application_conditions

    # 1. la normalisation est bien differenciee par colonne
    assert_vrai(NORMALISATION_TEXTE["type_raccordement"]("c") == "C",
                "type_raccordement doit etre normalise en MAJUSCULES ('AB', 'C')")
    for nom in ("type_fond", "situation"):
        assert_vrai(NORMALISATION_TEXTE[nom]("Elliptique") == "elliptique",
                    f"{nom} doit etre normalise en minuscules")

    # 2. un classeur portant les colonnes de configuration se relit correctement
    #    et le calcul aboutit, avec les 7 conditions d'application verifiees
    tmp = Path(tempfile.mkdtemp(prefix="codap_casse_"))
    try:
        src = Path(INPUT_EF_REF)
        dst = tmp / "input_CODAP.xlsx"
        convert_ef_to_codap(src, dst, type_fond="elliptique",
                            autoriser_fond_incompatible=True, verbose=False)
        data, _meta = read_input_codap(dst)

        assert_vrai("type_raccordement" in data,
                    "la colonne type_raccordement doit etre relue")
        lues = {v for v in data["type_raccordement"] if v is not None}
        assert_vrai(lues == {RACCORD_C},
                    f"type_raccordement relu {lues!r}, attendu {{{RACCORD_C!r}}} ; "
                    "une normalisation en minuscules reintroduirait le defaut")

        cond = check_application_conditions(data, raccordement=RACCORD_C)
        for c in ("delta2_egal_1", "h4_nul", "D3_egal_D4"):
            assert_vrai(c in cond,
                        f"la condition {c!r}, propre au raccordement type C, doit "
                        "etre evaluee et non silencieusement omise")

        # la chaine de calcul aboutit
        res = run_c975(data, verbose=False)
        assert_vrai(res["config"]["raccordement"] == RACCORD_C,
                    f"raccordement retenu {res['config']['raccordement']!r}")
        n = len(data["eu1"])
        assert_vrai(len(res["synthese"]["TENUE"]) == n,
                    f"{n} verdicts attendus")
        print(f"           {n} configurations calculees, 7 conditions verifiees")
    finally:
        gc.collect()
        shutil.rmtree(tmp, ignore_errors=True)

    # 3. une valeur non reconnue doit echouer, et non desactiver des controles
    factice = {k: np.ones(3) for k in ("eu1", "eu2", "eu3", "D1", "D3", "D4",
                                       "h4", "a1")}
    exc = attend_exception(ValueError, check_application_conditions,
                           factice, raccordement="type_inexistant")
    assert_vrai("raccordement" in str(exc).lower(),
                "le message doit nommer le parametre fautif ; obtenu : "
                f"{exc}")
    print("           un raccordement inconnu leve bien ValueError")


if __name__ == "__main__":
    sys.exit(_runner.executer(dict(globals()),
                              "Entrees/sorties et chaine complete"))
