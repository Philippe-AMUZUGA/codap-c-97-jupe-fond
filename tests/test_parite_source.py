"""
Parité avec le programme d'origine (`core/source/`) et avec les valeurs de référence.

Deux références :
  1. l'appel direct du programme d'origine (`codap_c97.runner.run_c975`), rejoué à chaque test, sans adaptateur ;
  2. `golden/golden.json` : les mêmes sorties relevées une fois sur six cas (départ, puis chaque autre choix) ;
Elles protègent l'adaptateur (correspondance des entrées, rangement des sorties) et signalent un changement
du programme d'origine ; sa justesse est établie par ses propres tests (`test_noyau_origine.py`) et par la validation
décrite dans le README. Un dernier test garde les fichiers d'origine intacts (empreintes SHA-256).

Relever de nouveau les valeurs de référence : `python tests/test_parite_source.py` depuis la racine (`src` et `tests`
dans PYTHONPATH).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from codap_c_97_jupe_fond.core import calculs
from codap_c_97_jupe_fond.core.schema import charger_schema, valider

from conftest import PAQUET

GOLDEN = Path(__file__).parent / "golden"
TOLERANCE = {"rtol": 1e-9, "atol": 1e-12}


def _cas() -> list[tuple[str, dict[str, Any]]]:
    """Valeurs de départ, puis chaque autre choix possible (le reste au départ)."""
    schema = charger_schema()
    base = valider(schema, {})
    cas: list[tuple[str, dict[str, Any]]] = [("valeurs_de_depart", base)]
    for champ in schema:
        if champ.type == "choix":
            cas += [(f"{champ.nom}={c}", {**base, champ.nom: c}) for c in champ.choix if c != base[champ.nom]]
    return cas


def _natif(valeur: Any) -> Any:
    element = np.asarray(valeur).reshape(-1)[0]
    return element.item() if hasattr(element, "item") else element


def _reference(entrees: dict[str, Any]) -> dict[str, Any]:
    """Sorties du programme d'origine appelé directement, rangées sous les clés des mesures et des tableaux."""
    donnees = {nom: np.array([float(entrees[nom])]) for nom in calculs.INPUT_COLUMNS}
    brut = calculs.run_c975(donnees, type_fond=entrees["type_fond"], situation=entrees["situation"], verbose=False)
    synthese = {k: _natif(v) for k, v in brut["synthese"].items()}
    comprime, tendu = brut["sides"]
    attendu: dict[str, Any] = {
        "verdict": str(synthese["verdict"]),
        "taux": synthese["taux_utilisation_max"],
        "cote_determinant": synthese["cote_determinant"],
        "critere_determinant": synthese["critere_determinant"],
    }
    for cote in (comprime, tendu):
        nom = cote["cote"]
        attendu[f"verdict_{nom}"] = "TENUE : OK" if _natif(cote["adm"]["ok_global"]) else "TENUE : non-OK"
        attendu[f"taux_{nom}"] = _natif(cote["adm"]["taux_max"])
        attendu[f"critere_{nom}"] = _natif(cote["adm"]["critere_determinant"])
    attendu |= {
        "applicable": synthese["applicable"],
        "dans_domaine_c9a6": synthese["dans_domaine_C9A6"],
        "hors_domaine_interaction": synthese["hors_domaine"],
        "reference": [[k, _natif(comprime["R"][k]), _natif(tendu["R"][k])] for k in comprime["R"]],
        "coefficients": [[k, _natif(brut[k])] for k in ("delta1", "delta2", "lambda1")]
        + [[k, _natif(v)] for k, v in brut["Cij"].items()],
        "contraintes": [
            [k, _natif(sc[k]), _natif(st[k])]
            for sc, st in zip(comprime["stresses"], tendu["stresses"], strict=True)
            for k in sc
        ],
        "criteres": [
            [k, comprime["_adm_obj"].equations.get(k, ""), _natif(comprime["adm"][k]), _natif(tendu["adm"][k])]
            for k in comprime["adm"]
        ],
    }
    return attendu


def _rendu(entrees: dict[str, Any]) -> dict[str, Any]:
    resultat = calculs.calculer(entrees)
    obtenu: dict[str, Any] = {m.cle: m.valeur for m in resultat.mesures}
    obtenu.update({tableau.cle: [list(ligne) for ligne in tableau.lignes] for tableau in resultat.tableaux})
    return obtenu


def _egal(obtenue: Any, attendue: Any) -> bool:
    if isinstance(attendue, list):
        return (
            isinstance(obtenue, list)
            and len(obtenue) == len(attendue)
            and all(_egal(o, a) for o, a in zip(obtenue, attendue, strict=True))
        )
    if isinstance(attendue, float):
        return obtenue == pytest.approx(attendue, rel=TOLERANCE["rtol"], abs=TOLERANCE["atol"])
    return obtenue == attendue


CAS = _cas()
CHEMIN_GOLDEN = GOLDEN / "golden.json"
REFERENCES = json.loads(CHEMIN_GOLDEN.read_text(encoding="utf-8"))["cas"] if CHEMIN_GOLDEN.is_file() else []


@pytest.mark.parametrize(("nom", "entrees"), CAS, ids=[c[0] for c in CAS])
def test_l_adaptateur_rend_ce_que_rend_le_programme_d_origine(nom: str, entrees: dict[str, Any]) -> None:
    attendu, obtenu = _reference(entrees), _rendu(entrees)
    assert set(obtenu) == set(attendu), "une sortie manque ou s'ajoute"
    for cle, valeur in attendu.items():
        assert _egal(obtenu[cle], valeur), f"{nom} : {cle}"


@pytest.mark.parametrize("cas", REFERENCES, ids=[c["nom"] for c in REFERENCES])
def test_les_valeurs_de_reference_sont_retrouvees(cas: dict[str, Any]) -> None:
    obtenu = _rendu(valider(charger_schema(), cas["entrees"]))
    assert set(obtenu) == set(cas["attendu"]), cas["nom"]
    for cle, valeur in cas["attendu"].items():
        assert _egal(obtenu[cle], valeur), f"{cas['nom']} : {cle}"


def test_le_golden_couvre_chaque_choix() -> None:
    assert [c["nom"] for c in REFERENCES] == [nom for nom, _ in CAS]


def test_les_fichiers_d_origine_sont_intacts() -> None:
    """Chaque fichier d'origine garde l'empreinte SHA-256 du manifeste (fins de ligne en LF pour un texte)."""
    dossier = PAQUET / "core" / "source"
    manifeste = json.loads((dossier / "EMPREINTES.json").read_text(encoding="utf-8"))["fichiers"]
    assert len(manifeste) >= 20
    for nom, attendue in manifeste.items():
        contenu = (dossier / nom).read_bytes()
        if (dossier / nom).suffix in {".py", ".txt", ".md"}:
            contenu = contenu.replace(b"\r\n", b"\n")
        assert hashlib.sha256(contenu).hexdigest() == attendue, nom
    presents = {
        p.relative_to(dossier).as_posix()
        for p in dossier.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.name != "EMPREINTES.json"
    } - {"__init__.py"}
    assert presents == set(manifeste), "un fichier d'origine n'a pas d'empreinte, ou l'inverse"


def ecrire_golden() -> None:
    """Relève les valeurs de référence en appelant directement le programme d'origine sur chaque cas."""
    contenu = {
        "schema": "GOLDEN_PYTHON/1",
        "source": "core/source/codap_c97 (run_c975)",
        "tolerance": TOLERANCE,
        "note": "relevé du programme d'origine appelé directement : protège l'adaptateur, ne prouve pas le calcul",
        "cas": [{"nom": nom, "entrees": entrees, "attendu": _reference(entrees)} for nom, entrees in _cas()],
    }
    CHEMIN_GOLDEN.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ecrire_golden()
    print(f"Valeurs de référence écrites dans {GOLDEN / 'golden.json'}")
