"""Export : formats, empreintes, refus d'écraser, noms refusés, écriture d'un coup, formules neutralisées."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from codap_c_97_jupe_fond import textes
from codap_c_97_jupe_fond.core import calculs, export
from codap_c_97_jupe_fond.core.erreurs import ErreurAnnulation, ErreurExport
from codap_c_97_jupe_fond.core.resultat import Mesure, Resultat, TableauResultat
from codap_c_97_jupe_fond.core.schema import charger_schema, valider
from codap_c_97_jupe_fond.core.taches import Annulation


@pytest.fixture
def resultat(entrees_exemple: dict) -> Resultat:
    return calculs.calculer(valider(charger_schema(), entrees_exemple))


@pytest.fixture
def dossier(tmp_path: Path) -> Path:
    sortie = tmp_path / "sortie"
    sortie.mkdir()
    return sortie


def test_tous_les_formats_sont_ecrits_et_relus(resultat: Resultat, dossier: Path) -> None:
    ecrits = export.exporter(resultat, dossier, nom="Poutre d'essai")
    noms = sorted(p.name for p in ecrits)
    assert noms == sorted(export.fichiers_a_ecrire(resultat, "Poutre d'essai", export.FORMATS))
    assert sorted(p.name for p in dossier.iterdir()) == noms, "aucun fichier provisoire ne reste"
    classeur = load_workbook(dossier / "Poutre_d_essai.xlsx")
    assert len(classeur.sheetnames) == 1 + len(resultat.tableaux)
    feuille = classeur.worksheets[0]
    premiere = resultat.mesures[0]
    if isinstance(premiere.valeur, int | float) and not isinstance(premiere.valeur, bool):
        assert feuille["B2"].value == pytest.approx(premiere.valeur)
    else:
        assert feuille["B2"].value == premiere.valeur
    assert (feuille["C2"].value or "") == premiere.unite
    for k in range(1, len(resultat.figures) + 1):
        assert (dossier / f"Poutre_d_essai_figure{k}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_le_csv_suit_la_langue(dossier: Path) -> None:
    resultat = Resultat(entrees={}, mesures=(Mesure("grandeur", 1.5, "mm"),))
    textes.definir_langue("fr")
    export.exporter(resultat, dossier, nom="a", formats=("csv",))
    ligne = (dossier / "a_mesures.csv").read_text(encoding="utf-8-sig").splitlines()[1]
    assert ";" in ligne and "," in ligne.split(";")[1]  # séparateur ; et virgule décimale
    if "en" in textes.LANGUES:
        textes.definir_langue("en")
        export.exporter(resultat, dossier, nom="b", formats=("csv",))
        ligne = (dossier / "b_mesures.csv").read_text(encoding="utf-8-sig").splitlines()[1]
        assert ";" not in ligne and "." in ligne


def test_projet_json_porte_les_entrees_et_les_empreintes(resultat: Resultat, dossier: Path) -> None:
    ecrits = export.exporter(resultat, dossier, nom="p")
    projet = json.loads((dossier / "projet.json").read_text(encoding="utf-8"))
    assert projet["version_format"] == export.FORMAT_PROJET
    assert projet["entrees"] == resultat.entrees
    assert projet["mesures"][resultat.mesures[0].cle]["unite"] == resultat.mesures[0].unite
    autres = {p.name for p in ecrits if p.name != "projet.json"}
    assert set(projet["fichiers"]) == autres
    for nom, empreinte in projet["fichiers"].items():
        assert export.empreinte_fichier(dossier / nom) == empreinte


def test_un_fichier_existant_n_est_jamais_ecrase_sans_demande(resultat: Resultat, dossier: Path) -> None:
    export.exporter(resultat, dossier, nom="p", formats=("csv",))
    avant = (dossier / "p_mesures.csv").read_bytes()
    (dossier / "p_mesures.csv").write_text("a modifier", encoding="utf-8")
    with pytest.raises(ErreurExport, match="existent déjà"):
        export.exporter(resultat, dossier, nom="p", formats=("csv",))
    assert (dossier / "p_mesures.csv").read_text(encoding="utf-8") == "a modifier"
    assert sorted(export.fichiers_existants(resultat, dossier, "p", ("csv",))) == sorted(
        export.fichiers_a_ecrire(resultat, "p", ("csv",))
    )
    export.exporter(resultat, dossier, nom="p", formats=("csv",), ecraser=True)
    assert (dossier / "p_mesures.csv").read_bytes() == avant


@pytest.mark.parametrize(
    "nom",
    [
        "",
        "   ",
        "../evasion.csv",
        "..\\evasion.csv",
        "/absolu.csv",
        "C:\\absolu.csv",
        "con",
        "nul.txt",
        "a:b",
        "a|b",
        "x?",
        "fin. ",
    ],
)
def test_les_noms_qui_sortent_du_dossier_ou_reserves_sont_refuses(dossier: Path, nom: str) -> None:
    with pytest.raises(ErreurExport):
        export.chemin_dans_dossier(dossier, nom)


def test_un_nom_correct_reste_sous_le_dossier(dossier: Path) -> None:
    cible = export.chemin_dans_dossier(dossier, "resultats.xlsx")
    assert cible.parent == dossier.resolve()
    with pytest.raises(ErreurExport, match="n'existe pas"):
        export.chemin_dans_dossier(dossier / "absent", "a.csv")


def test_un_lien_ne_sort_pas_du_dossier(dossier: Path, tmp_path: Path) -> None:
    lien = dossier / "lien"
    try:
        lien.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("liens symboliques non disponibles")
    with pytest.raises(ErreurExport):
        export.chemin_dans_dossier(dossier, "lien/x.csv")


def test_format_inconnu_ou_vide_et_annulation(resultat: Resultat, dossier: Path) -> None:
    with pytest.raises(ErreurExport, match="inconnu"):
        export.exporter(resultat, dossier, formats=("pdf",))
    with pytest.raises(ErreurExport, match="au moins un format"):
        export.exporter(resultat, dossier, formats=())
    annulation = Annulation()
    annulation.demander()
    with pytest.raises(ErreurAnnulation):
        export.exporter(resultat, dossier, annulation=annulation)
    assert list(dossier.iterdir()) == []


def test_un_texte_qui_ressemble_a_une_formule_reste_un_texte(dossier: Path) -> None:
    piege = Resultat(
        entrees={"nom_cas": "=1+1"},
        mesures=(Mesure("fleche_max", "=cmd|' /C calc'!A0", ""),),
        tableaux=(TableauResultat("profil", ("col_x", "col_fleche"), (("@somme", 1.5),)),),
    )
    export.exporter(piege, dossier, nom="piege", formats=("xlsx", "csv"))
    cellule = load_workbook(dossier / "piege.xlsx").worksheets[0]["B2"]
    assert cellule.data_type == "s" and cellule.value.startswith("=")
    with open(dossier / "piege_profil.csv", encoding="utf-8-sig", newline="") as flux:
        lignes = list(csv.reader(flux, delimiter=";" if textes.langue() == "fr" else ","))
    assert lignes[1][0] == "'@somme"


def test_un_nombre_non_fini_devient_null_dans_le_projet(dossier: Path) -> None:
    infini = Resultat(entrees={}, mesures=(Mesure("rigidite", float("inf"), "N/mm"),))
    export.exporter(infini, dossier, nom="inf", formats=("json",))
    projet = json.loads((dossier / "projet.json").read_text(encoding="utf-8"))
    assert projet["mesures"]["rigidite"]["valeur"] is None


# ====================================================================
# Une figure enregistrée seule (bouton « Enregistrer l'image »)
# ====================================================================
def _figure() -> object:
    from matplotlib.figure import Figure

    figure = Figure(figsize=(3, 2))
    figure.subplots().plot([0, 1], [1, 0])
    return figure


@pytest.mark.parametrize(("nom", "debut"), [("courbe.png", b"\x89PNG"), ("courbe.svg", b"<?xml"), ("sans", b"\x89PNG")])
def test_une_figure_s_enregistre_en_png_ou_en_svg_selon_l_extension(dossier: Path, nom: str, debut: bytes) -> None:
    ecrit = export.enregistrer_figure(_figure(), dossier / nom)
    assert ecrit.is_file() and ecrit.read_bytes().startswith(debut)
    assert ecrit.suffix in (".png", ".svg") and sorted(p.name for p in dossier.iterdir()) == [ecrit.name]


def test_une_figure_refuse_un_format_inconnu_et_un_dossier_absent(dossier: Path) -> None:
    textes.definir_langue("fr")
    with pytest.raises(ErreurExport, match="png"):
        export.enregistrer_figure(_figure(), dossier / "courbe.jpg")
    with pytest.raises(ErreurExport):
        export.enregistrer_figure(_figure(), dossier / "absent" / "courbe.png")
    assert list(dossier.iterdir()) == []


# ====================================================================
# Projet enregistré : entrées structurées et état des écrans
# ====================================================================
def test_un_projet_garde_les_entrees_structurees_et_l_etat_des_ecrans(dossier: Path) -> None:
    from codap_c_97_jupe_fond.core import fichiers

    entrees = {"nom": "Cas", "facteurs": [{"nom": "A", "bas": 1.0, "haut": 2.0}]}
    etat = {"calcule": True, "ecrans": {"analyse": {"choix": "pareto"}}}
    chemin = fichiers.ecrire_projet(dossier / "projet_cas.json", entrees, etat)
    assert fichiers.lire_projet(chemin) == (entrees, etat)
    assert fichiers.lire_entrees(chemin) == entrees
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["version_format"] == fichiers.FORMAT_ENTREES == 2


def test_un_fichier_d_entrees_plat_ou_ancien_se_rouvre_sans_etat(dossier: Path) -> None:
    from codap_c_97_jupe_fond.core import fichiers
    from codap_c_97_jupe_fond.core.erreurs import ErreurSaisie

    plat = dossier / "plat.json"
    plat.write_text('{"a": 1}', encoding="utf-8")
    assert fichiers.lire_projet(plat) == ({"a": 1}, {})
    ancien = dossier / "ancien.json"
    ancien.write_text('{"version_format": 1, "entrees": {"a": 2}}', encoding="utf-8")
    assert fichiers.lire_projet(ancien) == ({"a": 2}, {})
    mauvais = dossier / "mauvais.json"
    mauvais.write_text('{"version_format": 2, "entrees": {"a": 2}, "etat": [1]}', encoding="utf-8")
    with pytest.raises(ErreurSaisie):
        fichiers.lire_projet(mauvais)
