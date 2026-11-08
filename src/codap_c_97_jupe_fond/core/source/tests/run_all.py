# coding: utf-8
"""
Execution de la suite complete SANS pytest.

    python tests/run_all.py

Equivalent, si pytest est disponible :

    python -m pytest tests/ -v

Code de sortie 0 si tous les tests passent, 1 sinon.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runner

#: Fichiers de test, dans l'ordre de lecture recommande
MODULES = ("test_coefficients", "test_c975_reference",
           "test_stability", "test_io_and_pipeline")


def main():
    total = echecs = 0
    detail = []
    for nom in MODULES:
        module = importlib.import_module(nom)
        code = _runner.executer(dict(vars(module)), f"{nom}.py")
        fonctions = [k for k, v in vars(module).items()
                     if k.startswith("test_") and callable(v)]
        total += len(fonctions)
        if code:
            echecs += 1
        detail.append((nom, len(fonctions), code))
        print()

    print("#" * 78)
    print("BILAN GLOBAL DE LA SUITE DE VALIDATION CODAP C9.7")
    print("#" * 78)
    for nom, n, code in detail:
        print(f"  {nom:26s} {n:3d} test(s)   {'OK' if code == 0 else 'ECHEC(S)'}")
    print(f"  {'TOTAL':26s} {total:3d} test(s)   "
          f"{'tous passes' if echecs == 0 else f'{echecs} fichier(s) en echec'}")
    print("#" * 78)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
