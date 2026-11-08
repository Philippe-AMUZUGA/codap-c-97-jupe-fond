"""Adaptateur du domaine : cas unique, classeur, comparaison EF (le calcul est celui du programme d'origine)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codap_c_97_jupe_fond.core import calculs
from codap_c_97_jupe_fond.core.entrees import valider_entrees
from codap_c_97_jupe_fond.core.erreurs import ErreurAnnulation, ErreurCalcul, ErreurSaisie
from codap_c_97_jupe_fond.core.schema import charger_schema, valider
from codap_c_97_jupe_fond.core.taches import Annulation

from conftest import RACINE


@pytest.fixture
def cas(entrees_exemple: dict) -> dict:
    return valider_entrees(entrees_exemple)


def _mesures(resultat) -> dict:
    return {m.cle: m.valeur for m in resultat.mesures}


def test_le_cas_de_l_exemple_donne_verdicts_par_cote_et_enveloppe(cas: dict) -> None:
    resultat = calculs.calculer(cas)
    m = _mesures(resultat)
    assert m["verdict_comprime"] == "TENUE : OK"
    assert m["verdict_tendu"] == "TENUE : non-OK"
    assert m["verdict"] == "TENUE : non-OK"
    assert m["taux"] == pytest.approx(max(m["taux_comprime"], m["taux_tendu"]))
    assert m["cote_determinant"] == "tendu"
    assert m["applicable"] is True
    assert set(resultat.entrees) == set(calculs.CLES_CAS)


def test_les_tableaux_portent_r1_a_r7_les_cij_les_12_contraintes_et_les_criteres(cas: dict) -> None:
    tableaux = {t.cle: t for t in calculs.calculer(cas).tableaux}
    assert [ligne[0] for ligne in tableaux["reference"].lignes] == [f"R{k}" for k in range(1, 8)]
    assert len(tableaux["contraintes"].lignes) == 12
    noms = [ligne[0] for ligne in tableaux["coefficients"].lignes]
    assert noms[:3] == ["delta1", "delta2", "lambda1"] and "C71" in noms
    equations = {ligne[1] for ligne in tableaux["criteres"].lignes}
    assert {"C9.7.5-32", "C9.7.5-36", "C9.7.5-52"} <= equations


def test_en_situation_d_essai_les_contraintes_thermiques_sont_nulles(cas: dict) -> None:
    reference = {ligne[0]: ligne[1:] for ligne in calculs.calculer(cas).tableaux[0].lignes}
    assert reference["R5"] == reference["R6"] == reference["R7"] == (0.0, 0.0)
    autre = {ligne[0]: ligne[1:] for ligne in calculs.calculer({**cas, "situation": "autre"}).tableaux[0].lignes}
    assert any(v != 0.0 for v in autre["R5"] + autre["R6"] + autre["R7"])


def test_fz_positif_comprime_la_section(cas: dict) -> None:
    """FZ positif en compression : σmx1 du côté comprimé baisse quand FZ augmente."""

    def sigma(fz: float) -> float:
        lignes = calculs.calculer({**cas, "FZ": fz}).tableaux[2].lignes
        return next(ligne[1] for ligne in lignes if ligne[0] == "sigma_mx1")

    assert sigma(40000.0) < sigma(20000.0)


def test_un_cas_hors_domaine_est_signale(cas: dict) -> None:
    m = _mesures(calculs.calculer({**cas, "eu2": 6.0}))  # δ2 = eu2/eu1 ≠ 1 : hors du raccordement C
    assert m["applicable"] is False


def test_une_epaisseur_nulle_est_refusee(cas: dict) -> None:
    with pytest.raises(ErreurSaisie):
        calculs.calculer({**cas, "eu1": 0.0})
    with pytest.raises(ErreurSaisie):
        valider(charger_schema(), {"eu3": "0"})


def test_le_calcul_s_annule(cas: dict) -> None:
    jeton = Annulation()
    jeton.demander()
    with pytest.raises(ErreurAnnulation):
        calculs.calculer(cas, jeton)


def test_le_classeur_de_reference_est_calcule_par_lot() -> None:
    lot = calculs.traiter_classeur(RACINE / "examples" / "input_CODAP.xlsx", "elliptique", "autre")
    m = _mesures(lot.resultat)
    assert m["cas"] == 117
    assert 0 <= m["cas_tenue"] <= 117
    assert len(lot.resultat.tableaux[0].lignes) == 117
    assert "TENUE" in lot.resultat.tableaux[0].colonnes


def test_un_classeur_ef_est_converti_puis_calcule(tmp_path: Path) -> None:
    lot = calculs.traiter_classeur(RACINE / "examples" / "input_EF.xlsx", "korbbogen", "essai", 2.0)
    assert _mesures(lot.resultat)["cas"] > 0
    assert "Rp02t" in lot.journal
    ecrits = calculs.exporter_classeur(lot, tmp_path)
    assert [p.name for p in ecrits] == ["output_CODAP.xlsx", "journal_CODAP.txt"]
    assert all(p.stat().st_size > 0 for p in ecrits)
    with pytest.raises(ErreurCalcul):
        calculs.exporter_classeur(lot, tmp_path)  # jamais d'écrasement


def test_un_fichier_qui_n_est_pas_un_classeur_est_refuse(tmp_path: Path) -> None:
    faux = tmp_path / "faux.xlsx"
    faux.write_text("pas un classeur", encoding="utf-8")
    with pytest.raises(ErreurCalcul):
        calculs.traiter_classeur(faux)
    with pytest.raises(ErreurCalcul):
        calculs.traiter_classeur(tmp_path / "absent.csv")


@pytest.fixture
def dossier_etude(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Les deux fichiers synthétiques de `examples/etude_exemple`, désignés comme dossier d'étude."""
    dossier = RACINE / "examples" / "etude_exemple"
    monkeypatch.setenv(calculs.VARIABLE_ETUDE, str(dossier))
    return dossier


def test_le_rejeu_donne_les_deux_matrices_et_leurs_metriques(dossier_etude: Path) -> None:
    resultat = calculs.rejouer()
    matrices = calculs.matrices_du_resultat(resultat)
    n = matrices["regle"]["N"]
    assert n == matrices["codap"]["N"] == 24
    for methode in ("codap", "regle"):
        m = matrices[methode]
        assert m["TP"] + m["FN"] + m["FP"] + m["TN"] == n
    assert len(resultat.figures) == 1
    assert len(resultat.tableaux[1].lignes) == n


def test_d_autres_reglages_changent_codap_mais_pas_la_regle(dossier_etude: Path) -> None:
    de_base = calculs.matrices_du_resultat(calculs.rejouer())
    autre = calculs.matrices_du_resultat(calculs.rejouer(bras=1.0))
    cles = ("TP", "FN", "FP", "TN")
    assert {k: autre["regle"][k] for k in cles} == {k: de_base["regle"][k] for k in cles}
    assert (
        autre["codap"]["TP"] >= de_base["codap"]["TP"]
    )  # un bras plus court réduit MZ : CODAP accepte au moins autant


def test_sans_donnees_le_rejeu_dit_ou_les_deposer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(calculs.VARIABLE_ETUDE, str(tmp_path / "vide"))
    with pytest.raises(ErreurCalcul) as erreur:
        calculs.rejouer()
    assert calculs.FICHIER_EF in str(erreur.value)
    assert str(tmp_path / "vide") in str(erreur.value)


def test_des_donnees_incoherentes_sont_refusees(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import shutil

    for nom in (calculs.FICHIER_EF, calculs.FICHIER_CONTINGENCE):
        shutil.copy2(RACINE / "examples" / "etude_exemple" / nom, tmp_path / nom)
    contingence = tmp_path / calculs.FICHIER_CONTINGENCE
    contingence.write_text(contingence.read_text(encoding="utf-8").replace("84.2", "99.9", 1), encoding="utf-8")
    monkeypatch.setenv(calculs.VARIABLE_ETUDE, str(tmp_path))
    with pytest.raises(ErreurCalcul):
        calculs.rejouer()


@pytest.mark.parametrize("reglage", [{"fond": "grc"}, {"bras": 0.0}, {"seuil": -1.0}, {"E": float("nan")}])
def test_des_reglages_de_rejeu_invalides_sont_refuses(reglage: dict) -> None:
    with pytest.raises(ErreurCalcul):
        calculs.rejouer(**reglage)


def test_matrice_et_cas_degeneres() -> None:
    import numpy as np

    m = calculs.matrice(np.array([True, False]), np.array([True, False]))
    assert (m["TP"], m["FN"], m["FP"], m["TN"], m["MCC"]) == (1, 0, 0, 1, 1.0)
    vide = calculs.matrice(np.array([True, True]), np.array([True, True]))
    assert vide["MCC"] != vide["MCC"]  # NaN : un seul classement, MCC indéfini
