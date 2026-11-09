"""
Adaptateur du domaine : vérification C9.7.5 d'un assemblage jupe-fond, calcul d'un classeur.

Le calcul lui-même est celui du programme d'origine, copié tel quel dans `core/source/` (paquet `codap_c97` et
`Preprocess.py`, empreintes dans `EMPREINTES.json`). Ce fichier ne recalcule rien : il valide, appelle le programme
d'origine, puis range ce qu'il rend en mesures, tableaux et figures.

Deux fonctions du domaine, une par écran de calcul :
  `calculer(entrees)`        un cas unique (les 35 grandeurs, le type de fond et la situation) ;
  `traiter_classeur(...)`     un classeur `input_CODAP.xlsx`, ou un classeur `input_EF.xlsx` converti par `Preprocess`.

Conventions mécaniques (celles du programme d'origine) : FZ positif en compression ; aucun effet de fond ajouté à FZ
(il est porté par C71·R1) ; MZ = F_vent × bras ; en situation d'essai, aucun effet thermique (R5 = R6 = R7 = 0).
"""

from __future__ import annotations

import hashlib
import math
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..textes import t
from .erreurs import ErreurCalcul, ErreurSaisie
from .resultat import Mesure, Resultat, TableauResultat
from .taches import Annulation, Progression

SOURCE = Path(__file__).resolve().parent / "source"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))  # le programme d'origine s'importe sous son propre nom, sans modification

from codap_c97.io_excel import INPUT_COLUMNS, read_input_codap, write_output_codap  # noqa: E402
from codap_c97.runner import run_c975  # noqa: E402
from Preprocess import DEFAUTS_MATERIAU, convert_ef_to_codap  # noqa: E402

__all__ = [
    "CLES_CAS",
    "LotClasseur",
    "calculer",
    "exporter_classeur",
    "traiter_classeur",
    "verifier_entrees",
]

Avancer = Callable[[Progression], None]

#: Les 37 entrées d'un cas : les 35 grandeurs du programme d'origine, le type de fond et la situation.
CLES_CAS: tuple[str, ...] = (*INPUT_COLUMNS, "type_fond", "situation")
#: Grandeurs dont le programme d'origine exige la stricte positivité (conditions C9.7.2 de `validation.py`).
STRICTEMENT_POSITIVES = ("eu1", "eu2", "eu3", "a1", "D1", "D3")

#: Taille maximale d'un classeur accepté, et de son contenu décompressé.
TAILLE_CLASSEUR_MAX = 50 * 1024**2
TAILLE_DECOMPRESSEE_MAX = 500 * 1024**2
LIGNES_CLASSEUR_MAX = 100_000


# ====================================================================
# Cas unique
# ====================================================================
def verifier_entrees(entrees: Mapping[str, Any]) -> None:
    """Contrôle d'ensemble d'un cas : les grandeurs qui divisent dans C9.7.5 sont strictement positives."""
    if not any(k in entrees for k in CLES_CAS):
        return
    fautes = {
        nom: t("saisie.minimum_exclu", champ=nom, borne="0") for nom in STRICTEMENT_POSITIVES if entrees[nom] <= 0
    }
    if fautes:
        raise ErreurSaisie("saisie.plusieurs", par_champ=fautes, n=len(fautes), premier=next(iter(fautes.values())))


def _scalaire(valeur: Any) -> Any:
    """Premier élément d'un tableau numpy de longueur 1, en type Python natif."""
    element = np.asarray(valeur).reshape(-1)[0]
    return element.item() if hasattr(element, "item") else element


def _verdict(tenue: bool) -> str:
    """Verdict au format du programme d'origine, identique dans toutes les langues."""
    return "TENUE : OK" if tenue else "TENUE : non-OK"


def _brut_du_noyau(entrees: Mapping[str, Any]) -> dict[str, Any]:
    donnees = {nom: np.array([float(entrees[nom])]) for nom in INPUT_COLUMNS}
    return run_c975(donnees, type_fond=entrees["type_fond"], situation=entrees["situation"], verbose=False)


def _tableaux_du_cas(brut: dict[str, Any]) -> tuple[TableauResultat, ...]:
    comprime, tendu = brut["sides"]
    reference = tuple((nom, _scalaire(comprime["R"][nom]), _scalaire(tendu["R"][nom])) for nom in comprime["R"])
    rapports = tuple((nom, _scalaire(brut[nom])) for nom in ("delta1", "delta2", "lambda1"))
    coefficients = rapports + tuple((nom, _scalaire(valeur)) for nom, valeur in brut["Cij"].items())
    contraintes = tuple(
        (nom, _scalaire(section_c[nom]), _scalaire(section_t[nom]))
        for section_c, section_t in zip(comprime["stresses"], tendu["stresses"], strict=True)
        for nom in section_c
    )
    equations = comprime["_adm_obj"].equations
    criteres = tuple(
        (nom, equations.get(nom, ""), _scalaire(comprime["adm"][nom]), _scalaire(tendu["adm"][nom]))
        for nom in comprime["adm"]
    )
    return (
        TableauResultat("reference", ("grandeur", "comprime", "tendu"), reference),
        TableauResultat("coefficients", ("grandeur", "valeur"), coefficients),
        TableauResultat("contraintes", ("grandeur", "comprime", "tendu"), contraintes),
        TableauResultat("criteres", ("grandeur", "equation", "comprime", "tendu"), criteres),
    )


def _controler_fini(tableaux: tuple[TableauResultat, ...]) -> None:
    for tableau in tableaux:
        for ligne in tableau.lignes:
            if any(isinstance(v, float) and not math.isfinite(v) for v in ligne):
                raise ErreurCalcul("calcul.non_fini", grandeur=ligne[0])


def calculer(entrees: dict[str, Any], annulation: Annulation | None = None, avancer: Avancer | None = None) -> Resultat:
    """Vérification C9.7.5 : références, coefficients, contraintes, critères et verdicts des deux côtés."""
    annulation = annulation or Annulation()
    annulation.verifier()
    verifier_entrees(entrees)
    brut = _brut_du_noyau(entrees)
    synthese = {nom: _scalaire(valeur) for nom, valeur in brut["synthese"].items()}
    mesures = [
        Mesure("verdict", _verdict(bool(synthese["TENUE"]))),
        Mesure("taux", float(synthese["taux_utilisation_max"])),
        Mesure("cote_determinant", str(synthese["cote_determinant"])),
        Mesure("critere_determinant", str(synthese["critere_determinant"])),
    ]
    for cote in brut["sides"]:
        nom = cote["cote"]
        mesures += [
            Mesure(f"verdict_{nom}", _verdict(bool(_scalaire(cote["adm"]["ok_global"])))),
            Mesure(f"taux_{nom}", float(_scalaire(cote["adm"]["taux_max"]))),
            Mesure(f"critere_{nom}", str(_scalaire(cote["adm"]["critere_determinant"]))),
        ]
    mesures += [
        Mesure("applicable", bool(synthese["applicable"])),
        Mesure("dans_domaine_c9a6", bool(synthese["dans_domaine_C9A6"])),
        Mesure("hors_domaine_interaction", bool(synthese["hors_domaine"])),
    ]
    tableaux = _tableaux_du_cas(brut)
    _controler_fini(tableaux)
    if avancer is not None:
        avancer(Progression(t("calcul.nom"), 1, 1, t("calcul.fait")))
    return Resultat({nom: entrees[nom] for nom in CLES_CAS}, tuple(mesures), tableaux)


# ====================================================================
# Classeur
# ====================================================================
@dataclass
class LotClasseur:
    """Calcul d'un classeur : le résultat affiché, et ce qu'il faut au programme d'origine pour écrire sa sortie."""

    resultat: Resultat
    donnees: dict[str, Any]
    brut: dict[str, Any]
    journal: str


def _controler_classeur(chemin: Path) -> None:
    """Refuse un fichier qui n'est pas un classeur xlsx raisonnable : taille, macros, liens externes."""
    if chemin.suffix.lower() != ".xlsx" or not chemin.is_file():
        raise ErreurCalcul("classeur.refus", nom=chemin.name)
    if chemin.stat().st_size > TAILLE_CLASSEUR_MAX:
        raise ErreurCalcul("classeur.refus", nom=chemin.name)
    try:
        with zipfile.ZipFile(chemin) as archive:
            membres = archive.infolist()
    except zipfile.BadZipFile:
        raise ErreurCalcul("classeur.refus", nom=chemin.name) from None
    noms = [m.filename.lower() for m in membres]
    if sum(m.file_size for m in membres) > TAILLE_DECOMPRESSEE_MAX or any(
        "vbaproject" in n or "externallinks/" in n for n in noms
    ):
        raise ErreurCalcul("classeur.refus", nom=chemin.name)


def _premiere_ligne(chemin: Path, feuille_preferee: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    """En-têtes et lignes de la feuille lue par le programme d'origine (la feuille nommée, sinon la première)."""
    from openpyxl import load_workbook

    classeur = load_workbook(chemin, read_only=True, data_only=True)
    try:
        nom = feuille_preferee if feuille_preferee in classeur.sheetnames else classeur.sheetnames[0]
        lignes = list(classeur[nom].iter_rows(values_only=True))
    finally:
        classeur.close()
    if not lignes or len(lignes) > LIGNES_CLASSEUR_MAX + 1:
        raise ErreurCalcul("classeur.refus", nom=chemin.name)
    entetes = [str(h).strip() if h is not None else "" for h in lignes[0]]
    return entetes, [r for r in lignes[1:] if any(v is not None for v in r)]


def traiter_classeur(
    chemin: str | Path,
    fond: str = "korbbogen",
    situation: str = "essai",
    bras: float = 2.0,
    annulation: Annulation | None = None,
    avancer: Avancer | None = None,
) -> LotClasseur:
    """Calcule un classeur `input_CODAP.xlsx` ; un classeur de géométrie EF est d'abord converti par `Preprocess`."""
    annulation = annulation or Annulation()
    chemin = Path(chemin)
    _controler_classeur(chemin)
    annulation.verifier()
    entetes, _lignes = _premiere_ligne(chemin, "input_CODAP")
    journal = [t("conventions"), f"{t('classeur.fichier')} : {chemin.name}"]
    journal.append(f"SHA-256 : {hashlib.sha256(chemin.read_bytes()).hexdigest()}")
    try:
        if "eu1" in entetes:
            donnees, _meta = read_input_codap(chemin)
        else:
            entetes_ef, lignes_ef = _premiere_ligne(chemin, "input_EF")
            if "H" not in entetes_ef:
                raise ErreurCalcul("classeur.colonnes", nom=chemin.name)
            rang_h = entetes_ef.index("H")
            hauteurs = np.array([float(r[rang_h]) for r in lignes_ef])
            with tempfile.TemporaryDirectory() as dossier:
                converti = Path(dossier) / "input_CODAP.xlsx"
                convert_ef_to_codap(
                    chemin,
                    converti,
                    type_fond=fond,
                    situation=situation,
                    bras_levier=bras * hauteurs,
                    autoriser_fond_incompatible=True,
                    defauts={"f": 150.0, "fj": 150.0, "E": 210000.0, "Rp02t": 235.0},
                    verbose=False,
                )
                donnees, _meta = read_input_codap(converti)
            journal.append(t("classeur.converti", bras=bras))
            journal.append(", ".join(f"{k} = {v}" for k, v in DEFAUTS_MATERIAU.items()))
    except (KeyError, ValueError, TypeError) as erreur:
        raise ErreurCalcul("classeur.lecture", nom=chemin.name, detail=str(erreur).splitlines()[0]) from None
    annulation.verifier()
    if avancer is not None:
        avancer(Progression(t("classeur.nom"), 1, 2))
    brut = run_c975(donnees, type_fond=fond, situation=situation, verbose=False)
    journal.append(brut["rapport_conditions"])
    synthese = brut["synthese"]
    colonnes = tuple(synthese)
    rangees = tuple(zip(*(np.asarray(synthese[c]).tolist() for c in colonnes), strict=True))
    tenue = np.asarray(synthese["TENUE"], bool)
    applicable = np.asarray(synthese["applicable"], bool)
    mesures = (
        Mesure("cas", len(tenue)),
        Mesure("cas_tenue", int(tenue.sum())),
        Mesure("cas_hors_domaine", int((~applicable).sum())),
    )
    resultat = Resultat(
        {"fichier": chemin.name, "type_fond": fond, "situation": situation, "bras": bras},
        mesures,
        (TableauResultat("synthese", colonnes, rangees),),
    )
    if avancer is not None:
        avancer(Progression(t("classeur.nom"), 2, 2))
    return LotClasseur(resultat, donnees, brut, "\n".join(journal))


def exporter_classeur(lot: LotClasseur, dossier: str | Path) -> list[Path]:
    """Écrit `output_CODAP.xlsx` (sortie du programme d'origine) et `journal_CODAP.txt` ; ne remplace aucun fichier."""
    dossier = Path(dossier)
    if not dossier.is_dir():
        raise ErreurCalcul("export.dossier_absent", dossier=str(dossier))
    cible, journal = dossier / "output_CODAP.xlsx", dossier / "journal_CODAP.txt"
    existants = [p.name for p in (cible, journal) if p.exists()]
    if existants:
        raise ErreurCalcul("export.existe", noms=", ".join(existants))
    write_output_codap(cible, lot.donnees, lot.brut)
    journal.write_text(lot.journal + "\n", encoding="utf-8")
    return [cible, journal]
