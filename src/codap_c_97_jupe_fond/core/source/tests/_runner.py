# coding: utf-8
"""
Harnais d'execution de la suite de validation -- INDEPENDANT DE PYTEST.

Chaque fichier `test_*.py` de ce repertoire est exploitable de deux facons :

    python -m pytest tests/ -v          (si pytest est installe)
    python tests/test_xxx.py            (execution directe, sans pytest)

Ce module fournit :
  - l'amorcage de `sys.path` vers `02-SRC_PYTHON`, de sorte que `codap_c97`
    soit importable quel que soit le repertoire courant ;
  - la localisation de la bibliotheque de ressources `00-BIB_DATA_RESSOURCES`,
    deduite de l'arborescence du projet et NON des variables d'environnement,
    afin que la suite soit reproductible ;
  - quelques primitives d'assertion produisant des messages exploitables
    (valeur attendue, valeur obtenue, ecart, reference CODAP) ;
  - `executer()`, qui appelle toutes les fonctions `test_*` d'un module dans
    leur ordre de definition et rend un code de sortie POSIX.

Ce fichier n'est pas un fichier de test : il ne contient aucune fonction
`test_*` et pytest ne le collecte donc pas.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# --------------------------------------------------------------------------
# Amorcage des chemins
# --------------------------------------------------------------------------
#: Racine des sources : 02-SRC_PYTHON
SRC_ROOT = Path(__file__).resolve().parents[1]
#: Racine du projet
PROJECT_ROOT = SRC_ROOT.parent
#: Bibliotheque de donnees et de references
DIR_RESSOURCES = PROJECT_ROOT / "00-BIB_DATA_RESSOURCES"

#: Classeur d'entree de reference (117 configurations)
INPUT_CODAP_REF = DIR_RESSOURCES / "input_CODAP.xlsx"
#: Classeur de geometrie EF de reference (fond GRC)
INPUT_EF_REF = DIR_RESSOURCES / "input_EF.xlsx"
#: Script historique servant de temoin de non-regression
SCRIPT_HISTORIQUE = DIR_RESSOURCES / "JupeFond_CODAP_C9-7_v2022.py"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# --------------------------------------------------------------------------
# Primitives d'assertion
# --------------------------------------------------------------------------
def assert_proche(obtenu, attendu, rtol=1e-8, atol=0.0, nom="valeur", ref=""):
    """
    Verifie |obtenu - attendu| <= atol + rtol*|attendu|, scalaire ou tableau.

    Le message d'echec porte la reference CODAP, la valeur attendue, la valeur
    obtenue et l'ecart relatif : c'est ce que doit contenir un constat de
    non-conformite exploitable.
    """
    import numpy as np

    o = np.asarray(obtenu, dtype=float)
    a = np.asarray(attendu, dtype=float)
    if o.shape != a.shape and a.size != 1 and o.size != 1:
        raise AssertionError(
            f"{nom} {ref}: formes incompatibles {o.shape} vs {a.shape}")
    with np.errstate(invalid="ignore", over="ignore"):
        ecart = np.abs(o - a)
        seuil = atol + rtol * np.abs(a)
        # deux infinis de meme signe sont egaux : inf - inf vaut NaN, l'egalite
        # exacte doit donc etre testee separement. Idem pour deux NaN.
        egal = (o == a) | (np.isnan(o) & np.isnan(a))
        mauvais = ~(ecart <= seuil) & ~egal
    if np.any(mauvais):
        i = int(np.argmax(np.where(mauvais, ecart - seuil, -np.inf)))
        ov = float(o.ravel()[i]) if o.size > 1 else float(o)
        av = float(a.ravel()[i]) if a.size > 1 else float(a)
        rel = abs(ov - av) / max(abs(av), 1e-300)
        raise AssertionError(
            f"{nom} {ref} : {int(np.count_nonzero(mauvais))} valeur(s) hors "
            f"tolerance (rtol={rtol:g}, atol={atol:g}).\n"
            f"    pire ecart a l'indice {i} : attendu = {av!r}, "
            f"obtenu = {ov!r}, ecart relatif = {rel:.3e}")


def assert_vrai(condition, message):
    """Assertion booleenne avec message obligatoire."""
    if not condition:
        raise AssertionError(message)


def attend_exception(types, fonction, *args, **kwargs):
    """
    Verifie que `fonction` leve l'une des exceptions `types` et la retourne.

    Remplace `pytest.raises`, de sorte que les tests restent executables sans
    pytest.
    """
    try:
        fonction(*args, **kwargs)
    except types as exc:
        return exc
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"exception attendue {types}, obtenue {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"exception attendue {types}, aucune levee")


# --------------------------------------------------------------------------
# Execution autonome
# --------------------------------------------------------------------------
def executer(module_globals, titre=""):
    """
    Appelle toutes les fonctions `test_*` du module, dans l'ordre de definition.

    Retourne 0 si tout passe, 1 sinon. Les fonctions attendant des parametres
    (fixtures pytest) sont signalees et comptees en erreur : la suite est
    volontairement ecrite sans fixture.
    """
    import inspect

    noms = [k for k, v in module_globals.items()
            if k.startswith("test_") and callable(v)]
    largeur = 78
    print("=" * largeur)
    print(titre or module_globals.get("__name__", "tests"))
    print("=" * largeur)

    ok, ko = [], []
    for nom in noms:
        fn = module_globals[nom]
        doc = (fn.__doc__ or "").strip().splitlines()
        resume = doc[0].strip() if doc else ""
        if inspect.signature(fn).parameters:
            ko.append((nom, "la fonction attend des parametres (fixture) : "
                            "non supporte en execution directe"))
            print(f"[ERREUR ] {nom}\n           parametres non supportes")
            continue
        try:
            fn()
        except Exception:  # noqa: BLE001
            ko.append((nom, traceback.format_exc()))
            print(f"[ECHEC  ] {nom}")
            if resume:
                print(f"           {resume}")
        else:
            ok.append(nom)
            print(f"[OK     ] {nom}")
            if resume:
                print(f"           {resume}")

    print("-" * largeur)
    print(f"BILAN : {len(ok)} reussi(s), {len(ko)} echec(s) sur {len(noms)}")
    for nom, tb in ko:
        print("-" * largeur)
        print(f"ECHEC : {nom}")
        print(tb)
    print("=" * largeur)
    return 0 if not ko else 1
