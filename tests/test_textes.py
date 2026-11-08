"""Textes : parité des langues, clés employées, typographie, nombres à la française ou à l'anglaise."""

from __future__ import annotations

import ast
import re
import tomllib

import pytest

from codap_c_97_jupe_fond import textes
from codap_c_97_jupe_fond.textes import champs_de, cles, definir_langue, existe, formater_nombre, lire_decimal, t

from conftest import CADRATIN, DEMI_CADRATIN, DOUBLE_TRAIT, NBSP, PAQUET

SECTIONS = (
    "app|aide|commun|pied|menu|journal|guide|apropos|erreur|saisie|fichier|formulaire|entrees|actions|resultats"
    "|export|rail|calcul|sortie|figure|ecran|poste|essai|diagnostic"
)
FORME_DE_CLE = re.compile(rf"^({SECTIONS})\.(?!(?:.*\.)?(?:toml|json|log|png|ico|csv|xlsx|py|md)$)[a-z0-9_.]+$")


def test_les_langues_ont_les_memes_cles_et_les_memes_champs() -> None:
    reference = cles("fr")
    assert len(reference) > 120
    for code in textes.LANGUES:
        assert cles(code) == reference, f"{code} : clés différentes de fr"
        definir_langue(code)
        for cle in reference:
            definir_langue("fr")
            champs_fr = champs_de(t(cle))
            definir_langue(code)
            assert champs_de(t(cle)) == champs_fr, f"{code}.{cle} : champs différents de fr"


def _sources_python():
    return sorted(PAQUET.rglob("*.py"))


def _cles_employees() -> tuple[set[str], set[str]]:
    """(clés écrites en toutes lettres, motifs des clés composées d'un champ `{...}`)."""
    litterales: set[str] = set()
    motifs: set[str] = set()
    for source in _sources_python():
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        morceaux = {id(v) for n in ast.walk(arbre) if isinstance(n, ast.JoinedStr) for v in n.values}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str) and id(noeud) not in morceaux:
                if FORME_DE_CLE.match(noeud.value):
                    litterales.add(noeud.value)
            elif (
                isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "t"
                and noeud.args
                and isinstance(noeud.args[0], ast.Constant)
                and isinstance(noeud.args[0].value, str)
            ):
                litterales.add(noeud.args[0].value)  # tout appel `t("...")` désigne une clé, quelle que soit sa forme
            elif isinstance(noeud, ast.JoinedStr) and all(
                isinstance(v, ast.Constant | ast.FormattedValue) for v in noeud.values
            ):
                forme = ast.unparse(noeud)[2:-1].replace("{{", "{")
                if FORME_DE_CLE.match(re.sub(r"\{[^}]*\}", "x", forme)):
                    motifs.add(forme)
    return litterales, motifs


def test_chaque_cle_ecrite_en_toutes_lettres_a_son_texte() -> None:
    litterales, _ = _cles_employees()
    assert litterales
    for code in textes.LANGUES:
        assert sorted(c for c in litterales if not existe(c, code)) == [], code


def test_chaque_cle_composee_a_au_moins_un_texte() -> None:
    _, motifs = _cles_employees()
    assert motifs
    for motif in motifs:
        # une clé composée peut aussi être le préfixe de plusieurs textes (`ecran.<cle>.aide` pour `.quoi`, `.pourquoi`)
        modele = re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[a-z0-9_]+", re.escape(motif)) + r"(\..+)?$")
        assert any(modele.match(c) for c in cles("fr")), f"aucun texte pour {motif}"


def test_chaque_ecran_declare_a_son_rail_son_titre_et_ses_trois_reperes() -> None:
    declaration = tomllib.loads((PAQUET / "donnees" / "application.toml").read_text(encoding="utf-8"))
    for code in textes.LANGUES:
        for ecran in declaration.get("ecran", []):
            for suite in ("titre", "aide.quoi", "aide.pourquoi", "aide.regarder"):
                assert existe(f"ecran.{ecran['cle']}.{suite}", code), (code, ecran["cle"], suite)
            assert existe(f"rail.{ecran['cle']}", code), (code, ecran["cle"])


def test_l_espace_insecable_est_posee_en_francais_seulement() -> None:
    definir_langue("fr")
    assert NBSP + ":" in t("essai.titre", nom="a", version="1") and " :" not in t("essai.titre", nom="a", version="1")
    assert t("export.nom_sort", nom="x").count("«" + NBSP) == 2
    if "en" in textes.LANGUES:
        definir_langue("en")
        assert NBSP not in t("essai.titre", nom="a", version="1")


def test_les_nombres_suivent_la_langue() -> None:
    definir_langue("fr")
    assert (
        formater_nombre(1234.5, 2) == "1234,50"
        and formater_nombre(0.1) == "0,1"
        and formater_nombre(210000.0) == "210000"
    )
    if "en" in textes.LANGUES:
        definir_langue("en")
        assert formater_nombre(1234.5, 2) == "1234.50"


def test_la_saisie_accepte_virgule_point_espaces_et_refuse_le_reste() -> None:
    assert lire_decimal("1 234,5") == 1234.5
    assert lire_decimal("1" + NBSP + "234,5") == 1234.5
    assert lire_decimal("-0.25") == -0.25
    assert lire_decimal("1e-3") == 0.001
    for mauvais in ("1,234.5", "12a", "", "+-1", "inf", "1__0"):
        with pytest.raises(ValueError):
            lire_decimal(mauvais)


def test_une_cle_absente_est_signalee_et_une_langue_inconnue_refusee() -> None:
    with pytest.raises(KeyError, match="absente"):
        t("inconnu.cle")
    with pytest.raises(ValueError, match="Langue inconnue"):
        definir_langue("de")


def test_les_textes_n_ont_ni_tiret_cadratin_ni_phrase_d_attente() -> None:
    for code in textes.LANGUES:
        definir_langue(code)
        for cle in cles(code):
            texte = t(cle)
            assert not any(c in texte for c in (CADRATIN, DEMI_CADRATIN)) and DOUBLE_TRAIT not in texte, (code, cle)
