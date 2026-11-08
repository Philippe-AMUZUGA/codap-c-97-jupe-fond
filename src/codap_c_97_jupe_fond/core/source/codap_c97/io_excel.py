# coding: utf-8
"""
Lecture de #INPUT_CODAP et ecriture de #OUTPUT_CODAP.

Le programme est concu pour un traitement PAR LOT : chaque ligne du classeur
d'entree decrit une configuration complete (geometrie, materiau, chargements),
et toutes les configurations sont evaluees en une passe vectorisee. C'est le
regime d'emploi requis par les etudes parametriques et par la confrontation aux
calculs par elements finis qui motivent ce developpement.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .config import (FOND_ELLIPTIQUE, RACCORD_C, SHEET_INPUT_CODAP,
                     SHEET_OUT_COEF, SHEET_OUT_MAIN, SHEET_OUT_SYNTH,
                     SITUATION_AUTRE)

__all__ = ["INPUT_COLUMNS", "read_input_codap", "write_output_codap"]

#: Les 35 grandeurs reglementaires attendues en entree, avec leur signification.
#: L'ordre est celui du classeur historique, conserve pour compatibilite.
INPUT_COLUMNS = {
    "a1": "Epaisseur de la gorge de la soudure de raccordement jupe-appareil (mm)",
    "D1": "Diametre interieur de l'enveloppe cylindrique (mm)",
    "D3": "Diametre interieur de l'enveloppe au droit de la section Z-Z (mm)",
    "D4": "Diametre interieur de la jupe au droit de la section X-X (mm)",
    "c": "Ecartement des fibres moyennes de la jupe et de l'enveloppe (mm)",
    "eu1": "Epaisseur utile de l'enveloppe cylindrique (mm)",
    "eu2": "Epaisseur utile de la jupe (mm)",
    "eu3": "Epaisseur utile du fond (mm)",
    "lg1": "Longueur de reference 1 (mm)",
    "lg2": "Longueur de reference 2 (mm)",
    "lg3": "Longueur de reference 3 (mm)",
    "h4": "Hauteur d'emboitement (mm) - nulle en raccordement type C",
    "wg1": "Ecart de forme 1 (mm)",
    "wg2": "Ecart de forme 2 (mm)",
    "wg3": "Ecart de forme 3 (mm)",
    "FZ": "Effort vertical global au droit de la section Z-Z (N), POSITIF en compression (sigma_mx = -FZ/(pi D3 eu1) hors pression)",
    "FY": "Effort vertical global a la base de la jupe, section Y-Y (N)",
    "MZ": "Moment global de flexion au droit de la section Z-Z (N.mm)",
    "MY": "Moment global de flexion a la base de la jupe, section Y-Y (N.mm)",
    "p": "Pression de calcul (MPa), positive interieure / negative exterieure",
    "T": "Temperature de calcul (degC)",
    "gB": "Gradient thermique au bas de la jupe (K/mm)",
    "gK": "Gradient thermique a la carre du fond (K/mm)",
    "gT": "Gradient thermique dans la jupe (K/mm)",
    "deltaTK": "Ecart de temperature affectant la carre du fond (K)",
    "deltaTT": "Ecart de temperature affectant la jupe (K)",
    "alphaK": "Coefficient de dilatation du fond (1/K)",
    "alphaT": "Coefficient de dilatation de la jupe (1/K)",
    "E": "Module d'elasticite a la temperature de calcul (MPa)",
    "Rp02t": "Limite d'elasticite conventionnelle a 0,2 % a la temperature T (MPa)",
    "f": "Contrainte nominale de calcul du metal de base (MPa)",
    "fj": "Contrainte nominale de calcul du joint soude (MPa)",
    "S": "Coefficient de securite complementaire (-)",
    "KS": "Coefficient de securite au flambage (-)",
    "phiS": "Coefficient de soudure (-)",
}

#: Normalisation de casse des colonnes de configuration.
#:
#: Elle ne peut PAS etre uniforme : les constantes du code n'ont pas la meme
#: casse selon la grandeur. `type_raccordement` vaut 'AB' ou 'C' (majuscules,
#: notation du CODAP), tandis que `type_fond` et `situation` valent
#: 'elliptique', 'korbbogen', 'autre', 'essai' (minuscules).
#:
#: Une normalisation uniforme en minuscules transformait 'C' en 'c', valeur qui
#: ne correspondait plus a la constante RACCORD_C. L'effet n'etait pas seulement
#: un refus de calcul : `check_application_conditions` cessait silencieusement de
#: verifier les trois conditions propres au type C (delta2 = 1, h4 = 0,
#: D3 = D4), et le compte rendu n'en portait plus trace. D'ou la normalisation
#: par colonne, et la validation stricte des valeurs en aval.
NORMALISATION_TEXTE = {
    "type_raccordement": str.upper,
    "type_fond": str.lower,
    "situation": str.lower,
}

#: Colonnes facultatives : configuration par ligne, et donnees de C9.7.6
OPTIONAL_COLUMNS = {
    "type_raccordement": f"Type de raccordement jupe-appareil ('{RACCORD_C}')",
    "type_fond": f"Type de fond ('{FOND_ELLIPTIQUE}' ou 'korbbogen')",
    "situation": f"Situation de calcul ('{SITUATION_AUTRE}' ou 'essai')",
    "e4": "Epaisseur utile de la jupe au droit de la section X-X (mm)",
    "Fcmax": "Effort de compression global maximal admissible, Annexe C9.A4 (N)",
    "Mmax": "Moment global de flexion maximal admissible, Annexe C9.A4 (N.mm)",
}


def read_input_codap(path, sheet=SHEET_INPUT_CODAP):
    """
    Lit le classeur d'entree.

    Retourne (data, meta) ou `data` associe a chaque nom de colonne un
    numpy.ndarray, et `meta` porte le nombre de lignes et la liste des colonnes
    facultatives effectivement presentes.

    Les colonnes numeriques sont converties en flottants ; les colonnes de
    configuration ('type_fond', 'situation', 'type_raccordement') restent des
    chaines. Une colonne d'index sans en-tete, telle que produite par pandas,
    est ignoree.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"classeur d'entree introuvable : {path}")

    # Le classeur est ferme dans un `finally` : en mode lecture seule, openpyxl
    # conserve une archive ouverte sur le fichier, et sous Windows celui-ci reste
    # verrouille tant qu'elle ne l'est pas. Une sortie par exception -- feuille
    # absente, colonne obligatoire manquante, feuille vide -- laisserait sinon le
    # fichier d'entree verrouille jusqu'au passage du ramasse-miettes.
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        if sheet not in wb.sheetnames:
            if len(wb.sheetnames) == 1:
                sheet = wb.sheetnames[0]
            else:
                raise KeyError(f"feuille {sheet!r} absente ; feuilles presentes : "
                               f"{wb.sheetnames}")
        ws = wb[sheet]

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise ValueError(f"la feuille {sheet!r} est vide")
        header = [(str(h).strip() if h is not None else None) for h in rows[0]]

        # colonnes utiles
        idx = {}
        for j, h in enumerate(header):
            if h and h not in idx:
                idx[h] = j

        missing = [c for c in INPUT_COLUMNS if c not in idx]
        if missing:
            raise KeyError(
                f"colonnes obligatoires absentes de {path.name} : {missing}\n"
                f"colonnes trouvees : {sorted(k for k in idx)}")

        body = [r for r in rows[1:] if any(v is not None for v in r)]
        n = len(body)
        if n == 0:
            raise ValueError(f"aucune ligne de donnees dans {path.name}")

        data = {}
        for name in list(INPUT_COLUMNS) + list(OPTIONAL_COLUMNS):
            if name not in idx:
                continue
            j = idx[name]
            col = [r[j] if j < len(r) else None for r in body]
            if name in NORMALISATION_TEXTE:
                norme = NORMALISATION_TEXTE[name]
                data[name] = np.array(
                    [norme(str(v).strip()) if v is not None else None for v in col],
                    dtype=object)
            else:
                data[name] = np.array(
                    [np.nan if v is None else float(v) for v in col], dtype=float)
    finally:
        wb.close()

    meta = {"n": n, "source": str(path), "sheet": sheet,
            "optionnelles": [c for c in OPTIONAL_COLUMNS if c in idx]}
    return data, meta


# --------------------------------------------------------------------------
# Ecriture
# --------------------------------------------------------------------------
_HDR = Font(bold=True, color="FFFFFF")
_HDR_FILL = PatternFill("solid", fgColor="1F3864")
_OK_FILL = PatternFill("solid", fgColor="C6EFCE")
_NOK_FILL = PatternFill("solid", fgColor="FFC7CE")
_WARN_FILL = PatternFill("solid", fgColor="FFEB9C")


#: Colonnes booleennes qui ne sont pas un verdict de tenue : « OK » y serait
#: trompeur (hors_domaine = True signifie un probleme, pas une reussite).
_COLONNES_OUI_NON = {"hors_domaine", "dans_domaine_C9A6", "applicable"}


def _write_sheet(ws, columns, notes=None):
    """Ecrit un tableau colonne par colonne, avec en-tete mis en forme."""
    names = list(columns)
    for j, name in enumerate(names, start=1):
        cell = ws.cell(1, j, name)
        cell.font = _HDR
        cell.fill = _HDR_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = max(11, min(26, len(name) + 4))
    if notes:
        for j, name in enumerate(names, start=1):
            if name in notes:
                ws.cell(1, j).comment = None
    n = len(next(iter(columns.values())))
    for j, name in enumerate(names, start=1):
        col = columns[name]
        for i in range(n):
            v = col[i]
            if isinstance(v, (np.bool_, bool)):
                if name in _COLONNES_OUI_NON:
                    v = "OUI" if v else "NON"
                else:
                    v = "OK" if v else "non-OK"
            elif isinstance(v, (np.integer,)):
                v = int(v)
            elif isinstance(v, (np.floating, float)):
                v = None if (v != v or np.isinf(v)) else float(v)
            elif isinstance(v, np.str_):
                v = str(v)
            ws.cell(i + 2, j, v)
    ws.freeze_panes = "A2"
    return n


def write_output_codap(path, data, results, meta=None):
    """
    Ecrit le classeur de resultats.

    Trois feuilles :
      - `resultats`  : entrees, R1..R7, contraintes des trois sections
                       critiques, criteres d'admissibilite et verdict, pour
                       chaque cote du moment global ;
      - `coefficients_Cij` : les 42 coefficients, pour audit ;
      - `synthese`   : une ligne par configuration, verdict enveloppe des deux
                       cotes, critere determinant et taux d'utilisation.
    """
    path = Path(path)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ---------------- feuille resultats ------------------------------------
    ws = wb.create_sheet(SHEET_OUT_MAIN)
    cols = {}
    for k in INPUT_COLUMNS:
        if k in data:
            cols[k] = data[k]
    for side in results["sides"]:
        tag = side["cote"]
        for i in range(1, 8):
            cols[f"R{i}_{tag}"] = side["R"][f"R{i}"]
        for s in side["stresses"]:
            for k, v in s.items():
                cols[f"{k}_{tag}"] = v
        adm = side["adm"]
        cols[f"sigma_m_max1_{tag}"] = adm["sigma_m_max1"]
        cols[f"v2_1_{tag}"] = adm["v2_1"]
        cols[f"k1_1_{tag}"] = adm["k1_1"]
        cols[f"sigma_ball1_{tag}"] = adm["sigma_ball1"]
        cols[f"section_critique_{tag}"] = adm["section_critique"]
        cols[f"sigma_mV_{tag}"] = adm["sigma_mV"]
        cols[f"v2_23_{tag}"] = adm["v2_23"]
        cols[f"k1_23_{tag}"] = adm["k1_23"]
        cols[f"sigma_ball_{tag}"] = adm["sigma_ball"]
        cols[f"C9.7.5-32_{tag}"] = adm["ok_membrane_1"]
        cols[f"C9.7.5-36_{tag}"] = adm["ok_flexion_1"]
        cols[f"C9.7.5-52_{tag}"] = adm["ok_flexion_23"]
        cols[f"TENUE_{tag}"] = adm["ok_global"]
    _write_sheet(ws, cols)

    # ---------------- feuille coefficients ---------------------------------
    wsc = wb.create_sheet(SHEET_OUT_COEF)
    ccols = {"delta1": results["delta1"], "delta2": results["delta2"],
             "lambda1": results["lambda1"]}
    ccols.update(results["Cij"])
    _write_sheet(wsc, ccols)

    # ---------------- feuille synthese -------------------------------------
    wss = wb.create_sheet(SHEET_OUT_SYNTH)
    syn = results["synthese"]
    _write_sheet(wss, syn)
    # coloration du verdict
    names = list(syn)
    if "TENUE" in names:
        j = names.index("TENUE") + 1
        for i in range(len(syn["TENUE"])):
            c = wss.cell(i + 2, j)
            c.fill = _OK_FILL if syn["TENUE"][i] else _NOK_FILL
            c.font = Font(bold=True)
    if "hors_domaine" in names:
        j = names.index("hors_domaine") + 1
        for i in range(len(syn["hors_domaine"])):
            if syn["hors_domaine"][i]:
                wss.cell(i + 2, j).fill = _WARN_FILL

    wb.save(path)
    return path
