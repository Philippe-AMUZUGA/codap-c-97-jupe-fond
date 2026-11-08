"""
Génère les exemples synthétiques de `examples/` : deux classeurs (entrées CODAP et géométrie EF) et un dossier d'étude.

Les valeurs sont inventées (aucune provenance, aucun sens mécanique pour les contraintes) : elles servent à montrer
le format des fichiers et à exercer les écrans. Reproductible : aucune part d'aléatoire. La ligne 0 du classeur
`input_CODAP.xlsx` est le cas de référence gravé dans les tests du programme d'origine.

Lancer depuis la racine du dépôt : `python outils/generer_exemples.py`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from codap_c_97_jupe_fond.core import calculs  # noqa: E402

DIAMETRES = (1000, 1500, 2000, 2500, 3000, 3500)
EPAISSEURS = (8, 12, 16, 20)
ZONES = [f"{z}_{c}" for z in ("Z1", "Z2", "Z3") for c in ("R",)] + [
    f"{z}_{c}" for z in ("Z1", "Z2", "Z3") for c in ("L",)
]


#: Ligne 0 de `input_CODAP.xlsx` : le cas de référence des tests du programme d'origine (`core/source/tests`).
CAS_DE_REFERENCE = {
    "D1": 984.0, "D3": 984.0, "D4": 984.0, "E": 196000.0, "FY": -741393.3473110502, "FZ": -741393.3473110502,
    "KS": 1.5, "MY": 0.0, "MZ": 0.0, "Rp02t": 241.0, "S": 1.2, "T": 100.0, "a1": 8.0, "alphaK": 1.15e-05,
    "alphaT": 1.15e-05, "c": 0.0, "deltaTK": 0.0, "deltaTT": 0.0, "eu1": 8.0, "eu2": 8.0, "eu3": 8.0, "f": 160.667,
    "fj": 154.667, "gB": -0.05, "gK": -0.05, "gT": 0.14, "h4": 0.0, "lg1": 1000.0, "lg2": 1000.0, "lg3": 300.0,
    "p": 1.0, "phiS": 0.7, "wg1": 0.0, "wg2": 0.0, "wg3": 0.0,
}  # fmt: skip
NOMBRE_CAS_CODAP = 117
EPAISSEURS_CODAP = (8, 10, 12, 16, 20, 25, 30, 40)


def classeur_codap() -> pd.DataFrame:
    """117 cas : le cas de référence, puis un balayage de diamètres, d'épaisseurs et de pressions."""
    lignes = [dict(CAS_DE_REFERENCE)]
    for i in range(1, NOMBRE_CAS_CODAP):
        d1 = round(940.0 + (3980.0 - 940.0) * i / (NOMBRE_CAS_CODAP - 1), 1)
        e = float(EPAISSEURS_CODAP[i % len(EPAISSEURS_CODAP)])
        p = float(1 + i % 5)
        effort = -0.975 * math.pi / 4.0 * d1**2 * p * (0.9 + 0.2 * abs(math.sin(i)))
        ligne = dict(CAS_DE_REFERENCE)
        ligne.update(D1=d1, D3=d1, D4=d1, a1=e, eu1=e, eu2=e, eu3=e, p=p, FZ=effort, FY=effort)
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def geometries() -> pd.DataFrame:
    lignes = []
    for e in EPAISSEURS:
        for d in DIAMETRES:
            lignes.append({"e": e, "D1": d, "ALPHA": 0, "H": d, "R1": d, "R2": d / 10, "H3": d, "D3": d})
    frame = pd.DataFrame(lignes)
    frame.index.name = "index"
    return frame


def contraintes_ef(g: pd.DataFrame) -> pd.DataFrame:
    """Contraintes unitaires inventées : croissent avec D1/e, avec un écart fixe entre zones et entre côtés."""
    rapport = (g["D1"] / g["e"]).to_numpy(float)
    sortie = pd.DataFrame(index=g.index)
    poids = {"P": 1.0, "T": 0.12, "W": 0.02}
    for jeu, w in poids.items():
        for k, zone in enumerate(ZONES):
            cote = 1.0 + 0.004 * (k // 3)
            sortie[f"{jeu}_TRESCA_LIN_{zone}"] = (
                w * (0.9 - 0.08 * (k % 3)) * cote * (0.5 * rapport + 0.0002 * rapport**2)
            )
        sortie[f"{jeu}_TRESCA_LIN_Check_L"] = 0.5 * sortie[f"{jeu}_TRESCA_LIN_Z1_L"]
    return sortie.round(4)


def main() -> None:
    g = geometries()
    ef = pd.concat([g, contraintes_ef(g)], axis=1)
    sortie = RACINE / "examples" / "etude_exemple"
    sortie.mkdir(parents=True, exist_ok=True)
    ef.to_csv(sortie / calculs.FICHIER_EF)

    sigma = calculs._contrainte_ef(ef)
    classe_ef = np.where(sigma <= 225.0, "R", "D")
    sigma_regle = sigma * (1.0 + 0.03 * np.sin(np.arange(len(ef))))
    classe_regle = np.where(sigma_regle <= 225.0, "R", "D")
    contingence = pd.DataFrame(
        {
            "index": ef.index,
            "e": ef["e"].astype(float),
            "D1": ef["D1"].astype(float),
            "H": ef["H"].astype(float),
            "sigma_ref": sigma,
            "classe_EF": classe_ef,
            "sigma_regle": sigma_regle,
            "classe_regle": classe_regle,
            "zone_max": "Z1_L",
        }
    ).set_index("index")
    contingence.to_csv(sortie / calculs.FICHIER_CONTINGENCE)

    # classeur de géométrie EF : le format d'entrée de `Preprocess`
    classeur = g[["e", "D1", "ALPHA", "H", "R1", "R2", "H3", "D3"]].copy()
    classeur.insert(3, "Pression", 1.0)
    classeur.insert(4, "F_vent", 10000.0)
    classeur.insert(5, "F_ext", 10000.0)
    classeur.index.name = None
    classeur.to_excel(RACINE / "examples" / "input_EF.xlsx", sheet_name="input_EF")
    classeur_codap().to_excel(RACINE / "examples" / "input_CODAP.xlsx", sheet_name="input_CODAP")
    print(
        f"{len(ef)} cas écrits ; classeur input_EF.xlsx régénéré ; {int((sigma <= 225).sum())} résistants sous 225 MPa"
    )
    assert math.isfinite(float(sigma.max()))


if __name__ == "__main__":
    main()
