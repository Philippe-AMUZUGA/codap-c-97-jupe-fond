"""Schéma des entrées et validation : types, bornes, choix, messages, lecture depuis une signature.

Les règles de validation sont testées sur un schéma écrit dans ce fichier : le même test vaut pour toute
application, quelles que soient ses entrées. Le schéma réel de l'application est contrôlé à part, en bas.
"""

from __future__ import annotations

from typing import Literal

import pytest

from codap_c_97_jupe_fond import textes
from codap_c_97_jupe_fond.core.erreurs import ErreurSaisie
from codap_c_97_jupe_fond.core.schema import TYPES, Champ, champs_depuis_signature, charger_schema, valider

#: Un champ de chaque type, avec des bornes et des textes en français et en anglais.
SCHEMA: tuple[Champ, ...] = (
    Champ(
        "nom",
        "texte",
        defaut="Cas 1",
        libelle={"fr": "Nom du cas", "en": "Case name"},
        aide={"fr": "Nom de base.", "en": "Base name."},
    ),
    Champ(
        "mode",
        "choix",
        defaut="un",
        choix=("un", "deux"),
        etiquettes={"un": {"fr": "Premier", "en": "First"}, "deux": {"fr": "Second", "en": "Second one"}},
        libelle={"fr": "Mode", "en": "Mode"},
        aide={"fr": "Un des deux modes.", "en": "One of the two modes."},
    ),
    Champ(
        "valeur",
        "reel",
        defaut=1000.0,
        unite="N",
        minimum=1.0,
        maximum=1000000.0,
        libelle={"fr": "Valeur", "en": "Value"},
        aide={"fr": "Valeur réelle.", "en": "Real value."},
    ),
    Champ(
        "autre",
        "reel",
        defaut=500.0,
        libelle={"fr": "Autre", "en": "Other"},
        aide={"fr": "Autre valeur.", "en": "Other value."},
    ),
    Champ(
        "rang",
        "entier",
        defaut=51,
        minimum=2,
        maximum=5000,
        libelle={"fr": "Rang", "en": "Rank"},
        aide={"fr": "Un entier.", "en": "An integer."},
    ),
    Champ(
        "actif",
        "booleen",
        defaut=True,
        libelle={"fr": "Actif", "en": "Active"},
        aide={"fr": "Oui ou non.", "en": "Yes or no."},
    ),
    Champ(
        "facteurs",
        "tableau",
        defaut=[["A", 10.0, 20.0]],
        colonnes=(
            Champ("nom", "texte", defaut="X", libelle={"fr": "Nom", "en": "Name"}),
            Champ("bas", "reel", defaut=0.0, minimum=0.0, libelle={"fr": "Bas", "en": "Low"}),
            Champ("haut", "reel", defaut=1.0, libelle={"fr": "Haut", "en": "High"}),
        ),
        lignes_min=1,
        lignes_max=3,
        libelle={"fr": "Facteurs", "en": "Factors"},
        aide={"fr": "Un facteur par ligne.", "en": "One factor per row."},
    ),
)


@pytest.fixture
def schema() -> tuple[Champ, ...]:
    return SCHEMA


def test_chaque_defaut_du_schema_d_essai_est_valide(schema: tuple[Champ, ...]) -> None:
    assert {c.type for c in schema} == set(TYPES)
    valeurs = valider(schema, {})
    assert set(valeurs) == {c.nom for c in schema}


def test_la_virgule_et_le_point_decimaux_sont_acceptes(schema: tuple[Champ, ...]) -> None:
    assert valider(schema, {"valeur": "1 500,5"})["valeur"] == 1500.5
    assert valider(schema, {"valeur": "1500.5"})["valeur"] == 1500.5
    assert valider(schema, {"valeur": 2000})["valeur"] == 2000.0
    assert valider(schema, {"valeur": "1e3"})["valeur"] == 1000.0


def test_un_nombre_ambigu_ou_incorrect_est_refuse(schema: tuple[Champ, ...]) -> None:
    for brut in ("1,000.5", "abc", "1_000", "inf", "nan", "", True):
        with pytest.raises(ErreurSaisie) as erreur:
            valider(schema, {"valeur": brut})
        assert "valeur" in erreur.value.par_champ, brut


def test_les_bornes_sont_incluses_et_hors_bornes_refuse(schema: tuple[Champ, ...]) -> None:
    champ = next(c for c in schema if c.nom == "valeur")
    assert valider(schema, {"valeur": champ.minimum})["valeur"] == champ.minimum
    assert valider(schema, {"valeur": champ.maximum})["valeur"] == champ.maximum
    for hors in (champ.minimum - 0.5, champ.maximum + 1):
        with pytest.raises(ErreurSaisie):
            valider(schema, {"valeur": hors})


def test_les_bornes_strictes_refusent_la_valeur_limite_elle_meme(tmp_path) -> None:
    """`minimum_exclu` et `maximum_exclu` : la source écrit « x > 0 » ou « x < 10 », la limite est refusée."""
    fichier = tmp_path / "entrees.toml"
    fichier.write_text(
        '[[entree]]\nnom = "x"\ntype = "reel"\ndefaut = 1.0\nminimum = 0.0\nminimum_exclu = true\n'
        "maximum = 10.0\nmaximum_exclu = true\n",
        encoding="utf-8",
    )
    schema = charger_schema(fichier)
    assert (schema[0].minimum_exclu, schema[0].maximum_exclu) == (True, True)
    assert valider(schema, {"x": 0.001})["x"] == 0.001
    assert valider(schema, {"x": 9.999})["x"] == 9.999
    for limite in (0.0, 10.0, -1.0):
        with pytest.raises(ErreurSaisie):
            valider(schema, {"x": limite})
    for code in textes.LANGUES:
        textes.definir_langue(code)
        with pytest.raises(ErreurSaisie) as erreur:
            valider(schema, {"x": 0.0})
        assert "0" in erreur.value.par_champ["x"]
    textes.definir_langue("fr")


def test_un_champ_sans_borne_accepte_toute_valeur_finie(schema: tuple[Champ, ...]) -> None:
    assert valider(schema, {"autre": -1e9})["autre"] == -1e9


def test_un_entier_accepte_5_0_et_refuse_5_5(schema: tuple[Champ, ...]) -> None:
    assert valider(schema, {"rang": "5,0"})["rang"] == 5
    with pytest.raises(ErreurSaisie):
        valider(schema, {"rang": "5,5"})
    with pytest.raises(ErreurSaisie):
        valider(schema, {"rang": 1})  # sous le minimum


def test_booleens_et_choix(schema: tuple[Champ, ...]) -> None:
    for brut, attendu in (("oui", True), ("Faux", False), ("true", True), (0, False), (False, False)):
        assert valider(schema, {"actif": brut})["actif"] is attendu
    with pytest.raises(ErreurSaisie):
        valider(schema, {"actif": "peut-etre"})
    assert valider(schema, {"mode": "deux"})["mode"] == "deux"
    with pytest.raises(ErreurSaisie):
        valider(schema, {"mode": "libre"})


def test_un_texte_refuse_les_caracteres_de_controle_et_les_textes_trop_longs(schema: tuple[Champ, ...]) -> None:
    assert valider(schema, {"nom": "  Mon cas  "})["nom"] == "Mon cas"
    for brut in ("a\x00b", "x" * 201):
        with pytest.raises(ErreurSaisie):
            valider(schema, {"nom": brut})


def test_toutes_les_erreurs_sont_rassemblees_et_un_nom_inconnu_est_refuse(schema: tuple[Champ, ...]) -> None:
    with pytest.raises(ErreurSaisie) as erreur:
        valider(schema, {"valeur": "abc", "rang": -3, "inconnue": 1})
    assert set(erreur.value.par_champ) == {"valeur", "rang", "inconnue"}
    assert str(erreur.value).startswith(textes.t("saisie.plusieurs", n=3, premier="")[:12])


def test_les_messages_suivent_la_langue(schema: tuple[Champ, ...]) -> None:
    if "en" not in textes.LANGUES:
        pytest.skip("pas d'anglais à ce niveau")
    textes.definir_langue("en")
    with pytest.raises(ErreurSaisie) as erreur:
        valider(schema, {"valeur": "abc"})
    assert "a number is expected" in erreur.value.par_champ["valeur"]
    assert "Value" in erreur.value.par_champ["valeur"]


def test_un_schema_incoherent_est_refuse(tmp_path) -> None:
    fichier = tmp_path / "entrees.toml"
    fichier.write_text('[[entree]]\nnom = "a"\ntype = "complexe"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="type inconnu"):
        charger_schema(fichier)
    fichier.write_text('[[entree]]\nnom = "a"\ntype = "choix"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="choix"):
        charger_schema(fichier)
    fichier.write_text('[[entree]]\nnom = "a"\ntype = "reel"\n[[entree]]\nnom = "a"\ntype = "reel"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="répète"):
        charger_schema(fichier)


# ====================================================================
# Entrées structurées : le type tableau
# ====================================================================
def test_un_tableau_rend_des_lignes_typees_depuis_des_listes_ou_des_objets(schema: tuple[Champ, ...]) -> None:
    assert valider(schema, {})["facteurs"] == [{"nom": "A", "bas": 10.0, "haut": 20.0}]
    lignes = valider(schema, {"facteurs": [["B", "1,5", 2], {"nom": "C", "haut": "4"}]})["facteurs"]
    assert lignes == [{"nom": "B", "bas": 1.5, "haut": 2.0}, {"nom": "C", "bas": 0.0, "haut": 4.0}]


@pytest.mark.parametrize(
    ("brut", "motif"),
    [
        ("A;1;2", "tableau de lignes"),
        ([], "au moins 1"),
        ([["A", 1, 2]] * 4, "au plus 3"),
        ([["A", 1]], "ligne 1"),
        ([{"nom": "A", "inconnue": 1}], "ligne 1"),
        ([["A", 1, 2], ["B", -1, 2]], "ligne 2"),
        ([["A", 1, 2], ["B", "abc", 2]], "ligne 2"),
    ],
)
def test_un_tableau_mal_forme_est_refuse_avec_la_ligne_en_defaut(schema: tuple[Champ, ...], brut, motif: str) -> None:
    textes.definir_langue("fr")
    with pytest.raises(ErreurSaisie) as erreur:
        valider(schema, {"facteurs": brut})
    assert motif in erreur.value.par_champ["facteurs"]
    assert erreur.value.par_champ["facteurs"].startswith("Facteurs")


def test_un_tableau_se_declare_dans_entrees_toml(tmp_path) -> None:
    fichier = tmp_path / "entrees.toml"
    fichier.write_text(
        '[[entree]]\nnom = "points"\ntype = "tableau"\nlignes_min = 2\nlignes_max = 5\nformulaire = false\n'
        "defaut = [[0.0, true], [1.0, false]]\n"
        '[[entree.colonne]]\nnom = "x"\ntype = "reel"\nunite = "mm"\nminimum = 0.0\n'
        '[[entree.colonne]]\nnom = "actif"\ntype = "booleen"\n',
        encoding="utf-8",
    )
    (champ,) = charger_schema(fichier)
    assert (champ.type, champ.lignes_min, champ.lignes_max, champ.formulaire) == ("tableau", 2, 5, False)
    assert [c.nom for c in champ.colonnes] == ["x", "actif"] and champ.colonnes[0].unite == "mm"
    assert valider((champ,), {})["points"] == [{"x": 0.0, "actif": True}, {"x": 1.0, "actif": False}]


@pytest.mark.parametrize(
    ("declaration", "motif"),
    [
        ('[[entree]]\nnom = "t"\ntype = "tableau"\n', "colonnes"),
        ('[[entree]]\nnom = "t"\ntype = "tableau"\n[[entree.colonne]]\nnom = "a"\ntype = "tableau"\n', "type inconnu"),
        (
            '[[entree]]\nnom = "t"\ntype = "tableau"\n[[entree.colonne]]\nnom = "a"\ntype = "reel"\n'
            '[[entree.colonne]]\nnom = "a"\ntype = "reel"\n',
            "répète",
        ),
        (
            '[[entree]]\nnom = "t"\ntype = "tableau"\nlignes_min = 4\nlignes_max = 2\n'
            '[[entree.colonne]]\nnom = "a"\ntype = "reel"\n',
            "incohérents",
        ),
    ],
)
def test_un_tableau_mal_declare_est_refuse(tmp_path, declaration: str, motif: str) -> None:
    fichier = tmp_path / "entrees.toml"
    fichier.write_text(declaration, encoding="utf-8")
    with pytest.raises(ValueError, match=motif):
        charger_schema(fichier)


def test_la_validation_des_entrees_completes_ajoute_le_controle_d_ensemble_du_domaine(
    schema: tuple[Champ, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    from codap_c_97_jupe_fond.core import calculs
    from codap_c_97_jupe_fond.core.entrees import valider_entrees

    assert valider_entrees({}, schema) == valider(schema, {})

    def refuser(entrees: dict) -> None:
        if entrees["autre"] < 0:
            raise ErreurSaisie("erreur.refus", motif="autre négatif")

    monkeypatch.setattr(calculs, "verifier_entrees", refuser, raising=False)
    assert valider_entrees({"autre": 1.0}, schema)["autre"] == 1.0
    with pytest.raises(ErreurSaisie, match="autre négatif"):
        valider_entrees({"autre": -1.0}, schema)


def exemple(
    longueur: float,
    hauteur: float = 3.5,
    mode: Literal["un", "deux"] = "un",
    points: int = 4,
    actif: bool = True,
    nom: str = "x",
):
    return longueur, hauteur, mode, points, actif, nom


def test_un_formulaire_se_genere_depuis_une_signature() -> None:
    champs = champs_depuis_signature(exemple, unites={"longueur": "mm"}, bornes={"longueur": (1.0, None)})
    types = {c.nom: c.type for c in champs}
    assert types == {
        "longueur": "reel",
        "hauteur": "reel",
        "mode": "choix",
        "points": "entier",
        "actif": "booleen",
        "nom": "texte",
    }
    longueur = champs[0]
    assert (longueur.unite, longueur.minimum, longueur.maximum, longueur.defaut) == ("mm", 1.0, None, None)
    assert champs[2].choix == ("un", "deux") and champs[2].defaut == "un"
    assert champs[1].defaut == 3.5 and champs[3].defaut == 4
    # Aucune borne n'est inventée ; un paramètre sans défaut est obligatoire.
    assert all(c.minimum is None for c in champs[1:])
    with pytest.raises(ErreurSaisie):
        valider(champs, {})
    assert valider(champs, {"longueur": 2})["longueur"] == 2.0


def test_une_annotation_non_prise_en_charge_est_signalee() -> None:
    def fonction(x: list[int]) -> None: ...

    with pytest.raises(ValueError, match="non prise en charge"):
        champs_depuis_signature(fonction)


# ====================================================================
# Le schéma réel de l'application (donnees/entrees.toml)
# ====================================================================
def test_le_schema_de_l_application_se_lit_et_chaque_defaut_est_valide() -> None:
    reel = charger_schema()
    assert reel
    assert {c.type for c in reel} <= set(TYPES)
    assert set(valider(reel, {})) == {c.nom for c in reel}


def test_chaque_champ_de_l_application_a_ses_textes_dans_chaque_langue() -> None:
    for champ in charger_schema():
        for code in textes.LANGUES:
            assert champ.libelle.get(code), f"{champ.nom} : libellé absent ({code})"
            assert champ.aide_dans(code), f"{champ.nom} : aide absente ({code})"
            for valeur in champ.choix:
                assert champ.etiquette_dans(valeur, code), f"{champ.nom}.{valeur} : étiquette absente ({code})"


def test_les_valeurs_de_l_exemple_sont_valides(entrees_exemple: dict) -> None:
    reel = charger_schema()
    assert set(valider(reel, entrees_exemple)) == {c.nom for c in reel}
