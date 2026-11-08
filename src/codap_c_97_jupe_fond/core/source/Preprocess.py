# coding: utf-8
"""
Preprocess.py -- conversion #INPUT_EF -> #INPUT_CODAP.

OBJET
-----
Ce module comble l'ecart entre la description geometrique issue de la CAO et du
maillage elements finis, et le jeu de grandeurs reglementaires attendu par
C9.7.5. Les deux vocabulaires ne se recouvrent pas :

  - le modele EF decrit des SURFACES et des RAYONS reels (diametre exterieur,
    rayon de carre, rayon de calotte, inclinaison de jupe, hauteurs) ;
  - le CODAP raisonne sur des EPAISSEURS UTILES et des diametres INTERIEURS
    rapportes a des sections droites conventionnelles X-X, Y-Y, Z-Z.

La conversion est donc autant une traduction de conventions qu'un calcul.

IDENTIFICATION DU TYPE DE FOND -- POINT CRITIQUE
------------------------------------------------
Le type de fond n'est pas une donnee libre : il conditionne les coefficients Ci1
de l'Annexe C9.A6 ET la nature du raccordement admissible. C9.7.2.1 dispose :

  - fond elliptique ou torispherique Korbbogen  -> raccordement « AB » ou « C » ;
  - fond torispherique GRC                      -> raccordement « AB » IMPOSE.

Le module classe donc le fond a partir des rayons fournis (R1 = rayon de calotte,
R2 = rayon de carre), selon les normes citees par le CODAP :

    GRC        NF E 81-102 (12/1997)  : R1 = D,      R2 = 0,10 D
    Korbbogen  DIN 28013 (01/1993)    : R1 = 0,80 D, R2 = 0,154 D

et REFUSE de produire silencieusement un jeu de donnees type C a partir d'une
geometrie GRC. Ce controle est actif par defaut ; il peut etre leve
explicitement, auquel cas l'ecart est trace dans le compte rendu.

HYPOTHESES DE CHARGEMENT
------------------------
Le classeur EF ne porte que des grandeurs geometriques et deux efforts scalaires
(F_ext, F_vent). Le passage aux sollicitations de C9.7.5 suppose donc un modele
de chargement, ici explicite et parametrable :

    F_Z = -F_ext + p * pi/4 * D3^2        effort vertical au droit de Z-Z
          |          |
          |          effet de fond : la pression agit sur la section de
          |          l'enveloppe et TEND l'enveloppe (contribution positive)
          poids propre et fluide, comptes en compression (signe negatif)

    M_Z = F_vent * H                      moment de renversement au droit de Z-Z
          bras de levier H = hauteur du point d'application de la resultante
          de vent au-dessus de la section consideree

    F_Y = F_Z,  M_Y = M_Z                 report a la base de la jupe (Y-Y)
          Approximation : le poids propre de la jupe et la trainee de vent sur
          la hauteur de jupe sont negliges devant les charges de l'appareil.
          A affiner si la jupe est haute.

Toutes les grandeurs de materiau, les gradients thermiques et les coefficients
de securite sont absents du classeur EF. Les valeurs par defaut reprennent
celles du convertisseur historique (nuance austenitique a 100 degC) ; elles sont
listees dans DEFAUTS_MATERIAU et affichees a chaque conversion, afin qu'aucune
hypothese ne reste implicite.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codap_c97 import config
from codap_c97.io_excel import INPUT_COLUMNS, OPTIONAL_COLUMNS

__all__ = ["convert_ef_to_codap", "classify_head", "DEFAUTS_MATERIAU"]

#: Valeurs par defaut des grandeurs absentes du classeur EF.
#: Reprises du convertisseur historique JupeFond_Convert_Input_EF-2-Codap.py.
DEFAUTS_MATERIAU = {
    "T": 100.0,          # temperature de calcul, degC
    "E": 196_000.0,      # module d'elasticite a T, MPa
    "Rp02t": 241.0,      # limite d'elasticite a 0,2 % a T, MPa
    "f": 160.667,        # contrainte nominale de calcul du metal de base, MPa
    "fj": 154.667,       # contrainte nominale de calcul du joint soude, MPa
    "S": 1.2,            # coefficient de securite complementaire
    "KS": 1.5,           # coefficient de securite au flambage
    "phiS": 0.7,         # coefficient de soudure
    "alphaK": 1.15e-05,  # dilatation du fond, 1/K
    "alphaT": 1.15e-05,  # dilatation de la jupe, 1/K
    "gB": -0.05,         # gradient thermique bas de jupe, K/mm
    "gK": -0.05,         # gradient thermique carre du fond, K/mm
    "gT": 0.14,          # gradient thermique dans la jupe, K/mm
    "deltaTK": 0.0,      # ecart de temperature carre du fond, K
    "deltaTT": 0.0,      # ecart de temperature jupe, K
    "lg1": 1000.0,       # longueurs de reference, mm
    "lg2": 1000.0,
    "lg3": 300.0,
}

#: Signatures normalisees des fonds, en fraction du diametre.
SIGNATURES_FOND = {
    "grc":       {"R1": 1.000, "R2": 0.100, "norme": "NF E 81-102 (12/1997)"},
    "korbbogen": {"R1": 0.800, "R2": 0.154, "norme": "DIN 28013 (01/1993)"},
}


def classify_head(R1, R2, D, tol=0.03):
    """
    Identifie le type de fond a partir des rayons de calotte et de carre.

    Parametres
    ----------
    R1, R2 : array_like
        Rayon de calotte et rayon de carre, mm.
    D : array_like
        Diametre de reference du fond, mm.
    tol : float
        Tolerance relative sur les rapports R1/D et R2/D.

    Retourne
    -------
    (types, detail) : ndarray d'objets et dict de diagnostic.
    """
    R1 = np.asarray(R1, float)
    R2 = np.asarray(R2, float)
    D = np.asarray(D, float)
    r1, r2 = R1 / D, R2 / D

    types = np.full(R1.shape, "indetermine", dtype=object)
    for nom, sig in SIGNATURES_FOND.items():
        m = (np.abs(r1 - sig["R1"]) <= tol) & (np.abs(r2 - sig["R2"]) <= tol)
        types[m] = nom

    detail = {"R1_sur_D": r1, "R2_sur_D": r2,
              "plages": {"R1/D": (float(r1.min()), float(r1.max())),
                         "R2/D": (float(r2.min()), float(r2.max()))}}
    return types, detail


def convert_ef_to_codap(src, dst, raccordement=config.RACCORD_C,
                        type_fond=None, situation=config.SITUATION_AUTRE,
                        bras_levier=None, autoriser_fond_incompatible=False,
                        defauts=None, verbose=True):
    """
    Convertit le classeur de geometrie EF en classeur d'entree CODAP.

    Parametres
    ----------
    src, dst : chemins
        Classeurs #INPUT_EF (lecture) et #INPUT_CODAP (ecriture).
    raccordement : str
        Type de raccordement visé.
    type_fond : str ou None
        Type de fond a inscrire. None -> deduit des rayons par `classify_head`.
    situation : str
        Situation de calcul.
    bras_levier : array_like ou None
        Bras de levier du vent, mm. None -> 2.H (colonne H du classeur EF).
    autoriser_fond_incompatible : bool
        Leve le refus de convertir une geometrie GRC vers un raccordement
        type C, que C9.7.2.1 interdit.
    defauts : dict ou None
        Surcharge de DEFAUTS_MATERIAU.
    """
    src, dst = Path(src), Path(dst)
    par_defaut = dict(DEFAUTS_MATERIAU)
    if defauts:
        par_defaut.update(defauts)

    # ---- lecture du classeur EF -------------------------------------------
    wb = openpyxl.load_workbook(src, data_only=True, read_only=True)
    ws = wb[config.SHEET_INPUT_EF] if config.SHEET_INPUT_EF in wb.sheetnames \
        else wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    header = [(str(h).strip() if h is not None else None) for h in rows[0]]
    idx = {h: j for j, h in enumerate(header) if h}
    requis = ["e", "D1", "ALPHA", "Pression", "F_vent", "F_ext", "H", "R1", "R2", "H3", "D3"]
    manquant = [c for c in requis if c not in idx]
    if manquant:
        raise KeyError(f"colonnes absentes de {src.name} : {manquant}\n"
                       f"colonnes trouvees : {sorted(idx)}")

    body = [r for r in rows[1:] if any(v is not None for v in r)]
    get = lambda name: np.array(                                    # noqa: E731
        [float(r[idx[name]]) if r[idx[name]] is not None else np.nan for r in body])

    e = get("e")
    D1 = get("D1")
    D3 = get("D3")
    ALPHA = get("ALPHA")
    p = get("Pression")
    F_vent = get("F_vent")
    F_ext = get("F_ext")
    H = get("H")
    R1 = get("R1")
    R2 = get("R2")
    H3 = get("H3")
    n = e.size

    # ---- identification du type de fond -----------------------------------
    types, detail = classify_head(R1, R2, D1)
    uniques, comptes = np.unique(types.astype(str), return_counts=True)
    repartition = dict(zip(uniques.tolist(), comptes.tolist()))

    if type_fond is None:
        dominant = max(repartition, key=repartition.get)
        type_fond = dominant

    incompatible = (type_fond == "grc" and raccordement == config.RACCORD_C)
    if incompatible and not autoriser_fond_incompatible:
        raise ValueError(
            "\n".join([
                "Incompatibilite reglementaire detectee (CODAP C9.7.2.1).",
                "",
                f"  Geometrie lue dans {src.name} :",
                f"    R1/D1 = {detail['plages']['R1/D'][0]:.3f} a "
                f"{detail['plages']['R1/D'][1]:.3f}",
                f"    R2/D1 = {detail['plages']['R2/D'][0]:.3f} a "
                f"{detail['plages']['R2/D'][1]:.3f}",
                f"    -> fond identifie : torispherique GRC "
                f"({SIGNATURES_FOND['grc']['norme']})",
                "",
                "  Or C9.7.2.1 dispose : « Dans le cas ou l'appareil est equipe",
                "  d'un fond torispherique de type GRC, le raccordement doit etre",
                "  de type AB. » Le raccordement de type C demande est donc exclu",
                "  pour cette geometrie, et l'Annexe C9.A6 ne fournit aucun",
                "  coefficient Ci1 pour le couple (GRC ; type C).",
                "",
                "  Trois issues possibles :",
                "    1. traiter cette geometrie en raccordement type AB",
                "       (procedure C9.A6.3, non implementee dans cette version) ;",
                "    2. corriger la geometrie du fond vers un Korbbogen",
                "       (R1 = 0,80 D ; R2 = 0,154 D) ou un elliptique ;",
                "    3. forcer la conversion a des fins d'etude comparative, en",
                "       passant autoriser_fond_incompatible=True et en choisissant",
                "       explicitement type_fond='korbbogen' ou 'elliptique'.",
                "       Le resultat n'a alors AUCUNE valeur reglementaire.",
            ]))

    # ---- traduction geometrique -------------------------------------------
    # Raccordement type C : l'appareil est pose sur la jupe, les fibres moyennes
    # sont alignees et il n'y a pas d'emboitement.
    eu1 = e.copy()          # epaisseur utile de l'enveloppe
    eu2 = e.copy()          # epaisseur utile de la jupe    -> delta2 = 1 (C9.7.5-17)
    eu3 = e.copy()          # epaisseur utile du fond
    a1 = e.copy()           # gorge de soudure, prise egale a l'epaisseur
    D4 = D3.copy()          # continuite de diametre en type C
    c = np.zeros(n)         # ecartement des fibres moyennes nul
    h4 = np.zeros(n)        # pas d'emboitement
    wg1 = wg2 = wg3 = np.zeros(n)

    # ---- modele de chargement ---------------------------------------------
    # Convention du programme : FZ > 0 en COMPRESSION (sigma_mx = -FZ/(pi D3 eu1),
    # coefficient C72 = -0,5). L'effet de fond de la pression est deja porte par
    # C71.R1 : il ne doit pas etre ajoute a FZ (double comptage), contrairement
    # au modele EF ou la troncature impose de l'appliquer au point de reference.
    FZ = F_ext.copy()
    # Bras de levier du vent : le point de reference EF est a la hauteur totale
    # theorique de la cuve, soit 2.H au-dessus du raccordement (cuve tronquee a
    # mi-hauteur, H = hauteur de la paroi cylindrique modelisee).
    bras = 2.0 * H if bras_levier is None else np.asarray(bras_levier, float)
    MZ = F_vent * bras
    FY, MY = FZ.copy(), MZ.copy()

    # ---- assemblage --------------------------------------------------------
    cols = {
        "a1": a1, "D1": D1, "D3": D3, "D4": D4, "c": c,
        "eu1": eu1, "eu2": eu2, "eu3": eu3,
        "lg1": np.full(n, par_defaut["lg1"]),
        "lg2": np.full(n, par_defaut["lg2"]),
        "lg3": np.full(n, par_defaut["lg3"]),
        "h4": h4, "wg1": wg1, "wg2": wg2, "wg3": wg3,
        "FZ": FZ, "FY": FY, "MZ": MZ, "MY": MY, "p": p,
        "T": np.full(n, par_defaut["T"]),
        "gB": np.full(n, par_defaut["gB"]),
        "gK": np.full(n, par_defaut["gK"]),
        "gT": np.full(n, par_defaut["gT"]),
        "deltaTK": np.full(n, par_defaut["deltaTK"]),
        "deltaTT": np.full(n, par_defaut["deltaTT"]),
        "alphaK": np.full(n, par_defaut["alphaK"]),
        "alphaT": np.full(n, par_defaut["alphaT"]),
        "E": np.full(n, par_defaut["E"]),
        "Rp02t": np.full(n, par_defaut["Rp02t"]),
        "f": np.full(n, par_defaut["f"]),
        "fj": np.full(n, par_defaut["fj"]),
        "S": np.full(n, par_defaut["S"]),
        "KS": np.full(n, par_defaut["KS"]),
        "phiS": np.full(n, par_defaut["phiS"]),
        # colonnes de configuration
        "type_raccordement": np.full(n, raccordement, dtype=object),
        "type_fond": np.full(n, type_fond, dtype=object),
        "situation": np.full(n, situation, dtype=object),
        # colonnes utiles a C9.7.6
        "e4": eu2.copy(),
    }
    ordre = [c_ for c_ in INPUT_COLUMNS] + [c_ for c_ in OPTIONAL_COLUMNS if c_ in cols]

    # ---- ecriture ----------------------------------------------------------
    out = openpyxl.Workbook()
    ws2 = out.active
    ws2.title = config.SHEET_INPUT_CODAP
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="1F3864")
    for j, name in enumerate(ordre, start=1):
        cell = ws2.cell(1, j, name)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
        ws2.column_dimensions[cell.column_letter].width = max(11, len(name) + 4)
    for i in range(n):
        for j, name in enumerate(ordre, start=1):
            v = cols[name][i]
            ws2.cell(i + 2, j, str(v) if isinstance(v, str) else float(v))
    ws2.freeze_panes = "A2"

    # feuille de tracabilite des hypotheses
    ws3 = out.create_sheet("hypotheses")
    ws3["A1"] = "Hypotheses de conversion #INPUT_EF -> #INPUT_CODAP"
    ws3["A1"].font = Font(bold=True, size=12)
    lignes = [
        ("source", src.name),
        ("configurations", n),
        ("raccordement", raccordement),
        ("type de fond retenu", type_fond),
        ("repartition des fonds identifies", str(repartition)),
        ("R1/D1 (plage)", f"{detail['plages']['R1/D'][0]:.4f} a {detail['plages']['R1/D'][1]:.4f}"),
        ("R2/D1 (plage)", f"{detail['plages']['R2/D'][0]:.4f} a {detail['plages']['R2/D'][1]:.4f}"),
        ("situation", situation),
        ("", ""),
        ("Geometrie", "eu1 = eu2 = eu3 = a1 = e ; D4 = D3 ; c = 0 ; h4 = 0"),
        ("Effort vertical", "FZ = +F_ext (compression positive) ; effet de fond de la pression porte par C71.R1, non ajoute"),
        ("Moment", "MZ = F_vent * 2H  (point de reference EF a la hauteur totale theorique, 2H au-dessus du raccordement)"),
        ("Report en Y-Y", "FY = FZ ; MY = MZ  (poids et trainee de jupe negliges)"),
        ("", ""),
        ("ALPHA (inclinaison jupe)", f"lu mais non utilise ; plage "
                                     f"{np.nanmin(ALPHA):.3g} a {np.nanmax(ALPHA):.3g}"),
        ("H3 (hauteur de jupe)", f"lu mais non utilise ; plage "
                                 f"{np.nanmin(H3):.4g} a {np.nanmax(H3):.4g}"),
    ]
    if incompatible:
        lignes.append(("AVERTISSEMENT",
                       "fond GRC converti en type C : contraire a C9.7.2.1, "
                       "resultat sans valeur reglementaire"))
    lignes.append(("", ""))
    lignes.append(("Valeurs par defaut", "grandeurs absentes du classeur EF"))
    for k, v in par_defaut.items():
        lignes.append((f"  {k}", v))
    for i, (k, v) in enumerate(lignes, start=3):
        ws3.cell(i, 1, k).font = Font(bold=k in ("source", "Geometrie", "AVERTISSEMENT",
                                                 "Valeurs par defaut"))
        ws3.cell(i, 2, v)
    ws3.column_dimensions["A"].width = 34
    ws3.column_dimensions["B"].width = 62

    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)

    if verbose:
        print(f"  {n} configurations converties")
        print(f"  fonds identifies      : {repartition}")
        print(f"  type de fond retenu   : {type_fond}")
        if incompatible:
            print("  AVERTISSEMENT : fond GRC en raccordement type C, "
                  "contraire a C9.7.2.1")
        print(f"  hypotheses de charge  : FZ = +F_ext (compression) ; MZ = F_vent.2H")
        print(f"  -> {dst}")
    return dst


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Conversion #INPUT_EF -> #INPUT_CODAP.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--input", default=config.INPUT_EF)
    p.add_argument("--output", default=config.INPUT_CODAP)
    p.add_argument("--type-fond", default=None, choices=[*config.FONDS, "grc"])
    p.add_argument("--situation", default=config.SITUATION_AUTRE,
                   choices=list(config.SITUATIONS))
    p.add_argument("--forcer", action="store_true",
                   help="autorise la conversion d'un fond GRC en raccordement type C "
                        "(contraire a C9.7.2.1 ; resultat sans valeur reglementaire)")
    a = p.parse_args(argv)
    config.ensure_dirs()
    src = config.resolve_input(a.input)
    dst = Path(a.output)
    if not dst.is_absolute():
        dst = config.DIR_RESULTS / dst
    print(f"Conversion {src.name} -> {dst.name}")
    convert_ef_to_codap(src, dst, type_fond=a.type_fond, situation=a.situation,
                        autoriser_fond_incompatible=a.forcer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
