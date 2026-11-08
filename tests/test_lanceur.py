"""Lanceur : fichiers, plage de Python, options et dépendances cohérents avec l'application, sans rien installer.

L'installation réelle (environnement, pip, hors ligne, échec, désinstallation) s'essaie avec le lanceur lui-même, dans
un dossier à part, avec l'accord de l'auteur pour pip. Ces tests lisent les fichiers du projet et appellent les
fonctions pures de `outils/amorce.py`. Sans lanceur dans le dossier (gabarit de code seul), le module est sauté.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

from codap_c_97_jupe_fond import PYTHON_MAX, PYTHON_MIN, SLUG, SLUG_MIN
from codap_c_97_jupe_fond import __main__ as principal

RACINE = Path(__file__).resolve().parents[1]
AMORCE = RACINE / "outils" / "amorce.py"

pytestmark = pytest.mark.skipif(not AMORCE.is_file(), reason="pas de lanceur dans ce dossier")


@pytest.fixture(scope="module")
def amorce() -> ModuleType:
    spec = importlib.util.spec_from_file_location("amorce_du_projet", AMORCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _options(analyseur) -> set[str]:
    return {s for action in analyseur._actions for s in action.option_strings}


def test_l_amorce_porte_l_identite_du_projet(amorce: ModuleType) -> None:
    assert (amorce.SLUG, amorce.SLUG_MIN, amorce.PAQUET) == (SLUG, SLUG_MIN, "codap_c_97_jupe_fond")
    assert (amorce.PY_MIN, amorce.PY_MAX) == (PYTHON_MIN, PYTHON_MAX)


def test_la_plage_de_python_est_relue_dans_pyproject(amorce: ModuleType) -> None:
    attendue = (amorce.version_en_tuple(PYTHON_MIN), amorce.version_en_tuple(PYTHON_MAX))
    assert amorce.lire_plage_python(RACINE) == attendue


def test_les_options_du_lanceur_sont_libres_dans_l_application(amorce: ModuleType) -> None:
    """Le lanceur transmet ses arguments au point d'entrée du paquet : aucune lettre du lanceur n'y est employée."""
    options_application = _options(principal._analyseur())
    assert not set(amorce.OPTIONS_LANCEUR) & options_application
    assert {"-t", "-s", "-V", "-v", "-h"} <= options_application
    assert set(amorce.OPTIONS_CONSOLE) <= options_application


def test_les_dependances_sont_figees_et_couvrent_les_modules_requis(amorce: ModuleType) -> None:
    fichier = RACINE / "requirements.txt"
    exigences = [
        ligne.strip()
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith(("#", "-"))
    ]
    assert exigences
    non_figees = [ligne for ligne in exigences if "==" not in ligne]
    noms = {re.sub(r"[-_.]+", "-", nom).lower() for nom in amorce.noms_dependances(fichier)}
    assert noms and non_figees == []
    distributions = importlib.metadata.packages_distributions()
    for module in principal.MODULES_REQUIS:
        if module == "tkinter":
            continue
        candidates = {re.sub(r"[-_.]+", "-", d).lower() for d in distributions.get(module, [module])}
        assert candidates & noms, f"{module} : aucun paquet de requirements.txt ne le fournit"


def test_l_empreinte_de_requirements_ignore_les_fins_de_ligne(amorce: ModuleType, tmp_path: Path) -> None:
    lf, crlf = tmp_path / "lf.txt", tmp_path / "crlf.txt"
    lf.write_bytes(b"a==1\nb==2\n")
    crlf.write_bytes(b"a==1\r\nb==2\r\n")
    assert amorce.empreinte_requirements(lf) == amorce.empreinte_requirements(crlf)
    crlf.write_bytes(b"a==1\r\nb==3\r\n")
    assert amorce.empreinte_requirements(lf) != amorce.empreinte_requirements(crlf)


def test_l_environnement_reste_dans_l_application_sauf_chemin_trop_long(amorce: ModuleType, tmp_path: Path) -> None:
    env = {"LOCALAPPDATA": str(tmp_path / "local"), "XDG_DATA_HOME": str(tmp_path / "local")}
    runtime, raison = amorce.choisir_runtime(tmp_path, env=env, windows=False)
    assert raison is None and runtime == tmp_path.resolve() / ".runtime"
    long = tmp_path / ("x" * 120)
    runtime, raison = amorce.choisir_runtime(long, env=env, windows=True)
    assert raison is not None and raison.startswith("chemin trop long")
    # premier repli sous CodapC97JupeFond ; si ce chemin dépasse encore la limite, second repli court `r-<empreinte8>`
    premier = runtime.parent.name == SLUG and runtime.name.startswith("runtime-")
    second = runtime.parent == (tmp_path / "local") and runtime.name.startswith("r-")
    assert premier or second, runtime
    assert amorce.choisir_runtime(long, env=env, windows=True) == (runtime, raison), "le choix est stable"


def test_les_fichiers_du_lanceur_ont_leurs_fins_de_ligne() -> None:
    bats = sorted(RACINE.glob("*.bat"))
    assert (RACINE / f"Lancer_{SLUG}.bat") in bats
    for bat in bats:
        brut = bat.read_bytes()
        assert b"\r\n" in brut and not re.search(rb"(?<!\r)\n", brut), bat.name
    for sh in RACINE.glob("*.sh"):
        brut = sh.read_bytes()
        assert brut.startswith(b"#!") and b"\r\n" not in brut, sh.name


def test_le_lanceur_windows_porte_la_plage_de_python_et_appelle_l_amorce() -> None:
    texte = (RACINE / f"Lancer_{SLUG}.bat").read_text(encoding="utf-8")
    assert PYTHON_MIN in texte and PYTHON_MAX in texte
    assert "outils\\amorce.py" in texte
