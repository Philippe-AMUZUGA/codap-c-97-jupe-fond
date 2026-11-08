# coding: utf-8
"""
Variables dynamiques et constantes du programme -- CODAP 2015 Div.2, C9.7.

Toutes les designations de fichiers et de repertoires sont centralisees ici sous
forme de variables dynamiques en MAJUSCULES, conformement a la convention
`#NOM_VARIABLE` du cahier des charges. Elles sont surchargeables par variable
d'environnement de meme nom, ce qui permet d'industrialiser les campagnes de
calcul sans modifier le code source :

    set INPUT_CODAP=mon_cas.xlsx
    python main_CODAP_C9-7.py
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Arborescence de travail
# --------------------------------------------------------------------------
#: Racine du projet (parent de 02-SRC_PYTHON)
WORKDIR = Path(os.environ.get("WORKDIR", Path(__file__).resolve().parents[2]))

DIR_RESSOURCES = Path(os.environ.get("DIR_RESSOURCES", WORKDIR / "00-BIB_DATA_RESSOURCES"))
DIR_COMPETENCES = Path(os.environ.get("DIR_COMPETENCES", WORKDIR / "01-COMPETENCES"))
DIR_SRC = Path(os.environ.get("DIR_SRC", WORKDIR / "02-SRC_PYTHON"))
DIR_LATEX = Path(os.environ.get("DIR_LATEX", WORKDIR / "03-DOC_LATEX"))
RELEASE_DIR = Path(os.environ.get("RELEASE_DIR", WORKDIR / "_RELEASE_v01"))
DIR_RESULTS = Path(os.environ.get("DIR_RESULTS", WORKDIR / "04-RESULTATS"))

# --------------------------------------------------------------------------
# Fichiers d'echange
# --------------------------------------------------------------------------
#: Entree du module analytique principal (35 grandeurs reglementaires CODAP)
INPUT_CODAP = os.environ.get("INPUT_CODAP", "input_CODAP.xlsx")
#: Sortie enrichie : entrees + Rk + Cij + contraintes + verdicts
OUTPUT_CODAP = os.environ.get("OUTPUT_CODAP", "output_CODAP.xlsx")
#: Entree du module de pretraitement (grandeurs geometriques issues de la CAO/EF)
INPUT_EF = os.environ.get("INPUT_EF", "input_EF.xlsx")
#: Journal d'execution
LOG_FILE = os.environ.get("LOG_FILE", "logFile_CODAP_C9-7.txt")

#: Noms des feuilles Excel
SHEET_INPUT_CODAP = "input_CODAP"
SHEET_INPUT_EF = "input_EF"
SHEET_OUT_MAIN = "resultats"
SHEET_OUT_COEF = "coefficients_Cij"
SHEET_OUT_SYNTH = "synthese"

# --------------------------------------------------------------------------
# Constantes reglementaires
# --------------------------------------------------------------------------
#: Rapport contrainte circonferentielle / longitudinale de flexion,
#: impose forfaitairement par C9.7.5-22, -26 et -30.
RATIO_FLEXION_CIRCONFERENTIELLE = 0.3

#: Coefficient de l'interaction membrane-flexion, C9.7.5-34 et -50.
K1_FACTEUR = 1.5

#: Types de raccordement jupe-appareil (C9.7.2.1)
RACCORD_AB = "AB"          # appareil emboite dans la jupe
RACCORD_C = "C"            # appareil pose sur la jupe
RACCORDEMENTS = (RACCORD_AB, RACCORD_C)

#: Types de fond traites par l'Annexe C9.A6
FOND_ELLIPTIQUE = "elliptique"
FOND_KORBBOGEN = "korbbogen"
FOND_GRC = "grc"
FONDS = (FOND_ELLIPTIQUE, FOND_KORBBOGEN)

#: Situations de calcul (conditionne l'activation des contraintes thermiques)
SITUATION_AUTRE = "autre"   # exploitation normale, exceptionnelle...
SITUATION_ESSAI = "essai"   # epreuve hydraulique : R5 = R6 = R7 = 0
SITUATIONS = (SITUATION_AUTRE, SITUATION_ESSAI)

#: Cotes du moment global de flexion a examiner (C9.7.5, preambule)
COTE_COMPRIME = "comprime"
COTE_TENDU = "tendu"
COTES = (COTE_COMPRIME, COTE_TENDU)

# --------------------------------------------------------------------------
# Domaine de validite des regles (C9.7.2 / Annexe C9.A6)
# --------------------------------------------------------------------------
#: Bornes du rapport delta1 = eu3/eu1 couvertes par les abaques C9.A6
DELTA1_MIN, DELTA1_MAX = 0.5, 1.3
#: Bornes du rapport lambda1 = D1/eu2 couvertes par les abaques C9.A6
LAMBDA1_MIN, LAMBDA1_MAX = 30.0, 400.0
#: Borne du rapport lambda2 = h4/eu2 (raccordement type AB uniquement)
LAMBDA2_MIN, LAMBDA2_MAX = 0.0, 4.0


def ensure_dirs():
    """Cree les repertoires de sortie s'ils n'existent pas."""
    for d in (DIR_RESULTS, RELEASE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resolve_input(name: str) -> Path:
    """
    Localise un fichier d'entree.

    Recherche successivement : chemin absolu, repertoire courant, DIR_RESULTS,
    puis la bibliotheque de ressources DIR_RESSOURCES.
    """
    p = Path(name)
    if p.is_absolute():
        return p
    for base in (Path.cwd(), DIR_RESULTS, DIR_RESSOURCES):
        cand = base / p
        if cand.exists():
            return cand
    return Path.cwd() / p
