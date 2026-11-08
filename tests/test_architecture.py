"""Architecture : noyau sans interface, textes par clés, charte, style, versions, aucune écriture hors des données."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

from codap_c_97_jupe_fond import PYTHON_MIN, __version__
from codap_c_97_jupe_fond.core import calculs, export
from codap_c_97_jupe_fond.systeme import preferences

from conftest import CADRATIN, DEMI_CADRATIN, DOUBLE_TRAIT, PAQUET, RACINE

DOSSIERS_SANS_INTERFACE = ("core", "systeme", "textes")
SOURCE_D_ORIGINE = PAQUET / "core" / "source"
INTERDITS_DU_NOYAU = ("tkinter", "codap_c_97_jupe_fond.ui", "matplotlib.pyplot", "matplotlib.backends")


def _sources(*dossiers: str) -> list[Path]:
    """Fichiers Python des dossiers, sauf la source d'origine (copiée telle quelle : ses imports sont les siens)."""
    return sorted(p for d in dossiers for p in (PAQUET / d).rglob("*.py") if SOURCE_D_ORIGINE not in p.parents)


def _imports(source: Path) -> set[str]:
    """Noms de modules importés par un fichier, relatifs résolus contre le paquet."""
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    relatif = source.relative_to(PAQUET.parent).with_suffix("").parts[:-1]
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(a.name for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ""
            if noeud.level:
                racine = relatif[: len(relatif) - noeud.level + 1]
                base = ".".join([*racine, base]) if base else ".".join(racine)
            noms.add(base)
            noms.update(f"{base}.{a.name}" for a in noeud.names)
    return noms


@pytest.mark.parametrize("source", _sources(*DOSSIERS_SANS_INTERFACE), ids=lambda p: p.relative_to(PAQUET).as_posix())
def test_le_noyau_n_importe_aucune_interface(source: Path) -> None:
    """Le noyau, les services système et les textes ne dépendent ni de Tk, ni de `ui`, ni du moteur graphique."""
    trouves = [
        n for n in _imports(source) for interdit in INTERDITS_DU_NOYAU if n == interdit or n.startswith(interdit + ".")
    ]
    assert trouves == []


def test_le_noyau_n_importe_que_ses_voisins() -> None:
    """`core` ne remonte jamais vers `ui` ni vers l'essai ; `systeme` ne dépend pas de `core`."""
    for source in _sources("systeme"):
        assert not [n for n in _imports(source) if n.startswith("codap_c_97_jupe_fond.core")], source.name


# Appels d'interface dont l'argument de texte doit être une clé de texte, jamais une phrase en dur.
ARGUMENTS_DE_TEXTE = frozenset({"text", "title", "message", "label", "titre"})


def _appelle_t(noeud: ast.AST) -> bool:
    """Vrai si l'expression contient un appel `t(...)` (texte demandé par sa clé)."""
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "t" for n in ast.walk(noeud))


def test_aucun_texte_en_dur_dans_l_interface() -> None:
    """Tout texte affiché passe par `t(...)` : un littéral de chaîne dans `text=`, `title=`, `label=` est refusé."""
    fautes = []
    for source in _sources("ui"):
        for noeud in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(noeud, ast.Call):
                continue
            for mot in noeud.keywords:
                valeur = mot.value
                litteral = isinstance(valeur, ast.Constant) and isinstance(valeur.value, str) and valeur.value.strip()
                compose = isinstance(valeur, ast.JoinedStr) and not _appelle_t(
                    valeur
                )  # un f-string qui cite `t(...)` passe
                if mot.arg in ARGUMENTS_DE_TEXTE and (litteral or compose):
                    fautes.append(f"{source.name}:{noeud.lineno} {mot.arg}")
    assert fautes == []


@pytest.mark.parametrize("source", _sources("ui"), ids=lambda p: p.relative_to(PAQUET).as_posix())
def test_les_fonctions_d_interface_restent_courtes(source: Path) -> None:
    """Une fonction d'interface de plus de 60 lignes se découpe : difficile à relire et à tester (tronc 09)."""
    longues = []
    for noeud in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.FunctionDef) and noeud.end_lineno and noeud.end_lineno - noeud.lineno + 1 > 60:
            longues.append(noeud.name)
    assert longues == []


def _fichiers_du_projet() -> list[Path]:
    exclus = {"__pycache__", ".pytest_cache", ".ruff_cache", ".runtime", "vendor", ".git"}
    sortie = []
    for chemin in sorted(RACINE.rglob("*")):
        a_garder = chemin.is_file() and not exclus & set(chemin.relative_to(RACINE).parts)
        if a_garder and chemin.suffix in {".py", ".toml", ".json", ".md", ".txt", ".yml", ".bat", ".sh", ".cff"}:
            sortie.append(chemin)
    return sortie


def test_aucun_jeton_ni_reste_de_fabrication() -> None:
    """Aucun jeton entre chevrons, aucune phrase d'attente ni exception de remplissage dans le projet."""
    jeton = re.compile("<[A-Z][A-Z_]{2,}>")
    mots = ["à" + r"\s+compl" + "éter", "raise NotImplementedError", "X" * 3, "lorem " + "ipsum"]
    attente = re.compile("(" + "|".join(mots) + ")", re.IGNORECASE)
    fautes = []
    for chemin in _fichiers_du_projet():
        if chemin.name == Path(__file__).name or "core/source/" in chemin.as_posix():
            continue
        for rang, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
            if jeton.search(ligne) or attente.search(ligne):
                fautes.append(f"{chemin.relative_to(RACINE).as_posix()}:{rang}")
    assert fautes == []


def test_charte_aucun_tiret_long_dans_les_textes() -> None:
    """Aucun tiret long ni suite de deux traits : deux-points pour un titre, virgules pour une incise."""
    interdits = (CADRATIN, DEMI_CADRATIN, DOUBLE_TRAIT)
    fautes = []
    for chemin in _fichiers_du_projet():
        if chemin.name == Path(__file__).name or chemin.name.startswith("requirements"):
            continue
        if SOURCE_D_ORIGINE in chemin.parents:  # copiée telle quelle : sa typographie n'est pas la nôtre
            continue
        for rang, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
            if any(i in ligne for i in interdits):
                fautes.append(f"{chemin.relative_to(RACINE).as_posix()}:{rang}")
    assert fautes == []


def test_le_style_choisit_les_fichiers() -> None:
    """Un écran : `ecran_unique.py` seul. Parcours ou onglets : `rail.py` et `ecrans/` seuls. Jamais les deux."""
    style = tomllib.loads((PAQUET / "donnees" / "application.toml").read_text(encoding="utf-8"))["application"]["style"]
    assert style in {"un", "parcours", "onglets"}
    unique, rail = (PAQUET / "ui" / "ecran_unique.py").is_file(), (PAQUET / "ui" / "rail.py").is_file()
    assert unique == (style == "un")
    assert rail == (style != "un")
    assert (PAQUET / "ui" / "ecrans").is_dir() == (style != "un")


def test_les_ecrans_declares_existent() -> None:
    """Chaque `[[ecran]]` de application.toml a son fichier et sa classe (styles à rail)."""
    declaration = tomllib.loads((PAQUET / "donnees" / "application.toml").read_text(encoding="utf-8"))
    if declaration["application"]["style"] == "un":
        pytest.skip("style un : pas de rail")
    for ecran in declaration["ecran"]:
        arbre = ast.parse((PAQUET / "ui" / "ecrans" / f"{ecran['module']}.py").read_text(encoding="utf-8"))
        assert ecran["classe"] in {n.name for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)}


def test_la_version_et_la_plage_de_python_sont_coherentes() -> None:
    """`__version__` est la source unique ; pyproject la lit et déclare la même borne basse de Python."""
    pyproject = RACINE / "pyproject.toml"
    if not pyproject.is_file():
        pytest.skip("pas de pyproject.toml")
    contenu = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert contenu["tool"]["setuptools"]["dynamic"]["version"]["attr"].endswith(".__version__")
    assert contenu["project"]["requires-python"] == f">={PYTHON_MIN}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def _empreinte_du_dossier(dossier: Path) -> dict[str, tuple[int, int]]:
    return {
        p.relative_to(dossier).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(dossier.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_aucune_ecriture_dans_le_dossier_du_programme(tmp_path: Path, entrees_exemple: dict) -> None:
    """Calcul, export, préférences et journal ne modifient rien dans le dossier du programme."""
    avant = _empreinte_du_dossier(PAQUET.parent)
    from codap_c_97_jupe_fond.core.schema import charger_schema, valider
    from codap_c_97_jupe_fond.systeme import journal

    journal.installer()
    resultat = calculs.calculer(valider(charger_schema(), entrees_exemple))
    (tmp_path / "sortie").mkdir()
    export.exporter(resultat, tmp_path / "sortie")
    preferences.enregistrer(preferences.Preferences(theme="sombre"))
    journal.desinstaller()
    assert _empreinte_du_dossier(PAQUET.parent) == avant
