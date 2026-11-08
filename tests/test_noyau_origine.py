"""
Les 45 tests du programme d'origine, rejoués tels quels dans le dépôt (ils ne sont ni réécrits ni modifiés).

Le programme d'origine cherche ses ressources à côté de son dossier de sources (`00-BIB_DATA_RESSOURCES`) : le test
reconstitue cette arborescence dans un dossier temporaire, avec les copies conservées dans `core/source/`, les
classeurs de référence de `examples/` et le programme historique de 2022 (`core/source/temoin/`, témoin de
non-régression des coefficients, rangé sous l'extension .txt pour qu'il ne soit ni importé ni contrôlé comme du code
de l'application),
puis lance la suite d'origine (`tests/run_all.py`) dans un processus séparé.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import PAQUET, RACINE

SOURCE = PAQUET / "core" / "source"
HISTORIQUE = SOURCE / "temoin" / "JupeFond_CODAP_C9-7_v2022.py.txt"
NOMBRE_DE_TESTS = 45


def _arborescence(racine: Path) -> Path:
    sources = racine / "src"
    ressources = racine / "00-BIB_DATA_RESSOURCES"
    ignorer = shutil.ignore_patterns("__pycache__")
    shutil.copytree(SOURCE / "codap_c97", sources / "codap_c97", ignore=ignorer)
    shutil.copytree(SOURCE / "tests", sources / "tests", ignore=ignorer)
    shutil.copy2(SOURCE / "Preprocess.py", sources / "Preprocess.py")
    ressources.mkdir()
    for nom in ("input_CODAP.xlsx", "input_EF.xlsx"):
        shutil.copy2(RACINE / "examples" / nom, ressources / nom)
    shutil.copy2(HISTORIQUE, ressources / "JupeFond_CODAP_C9-7_v2022.py")
    return sources


def test_les_45_tests_du_programme_d_origine_passent(tmp_path: Path) -> None:
    sources = _arborescence(tmp_path)
    execution = subprocess.run(
        [sys.executable, "-X", "utf8", str(sources / "tests" / "run_all.py")],
        cwd=sources,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    sortie = execution.stdout + execution.stderr
    assert execution.returncode == 0, sortie[-3000:]
    total = re.search(r"TOTAL\s+(\d+) test\(s\)\s+tous passes", sortie)
    assert total is not None, sortie[-3000:]
    assert int(total.group(1)) == NOMBRE_DE_TESTS
