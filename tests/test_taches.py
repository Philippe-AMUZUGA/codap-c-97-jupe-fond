"""Tâches : résultat, échec avec trace, annulation, avancement, une seule exécution."""

from __future__ import annotations

import time

import pytest

from codap_c_97_jupe_fond.core.erreurs import ErreurAnnulation
from codap_c_97_jupe_fond.core.taches import EtatTache, Progression, Tache


def test_une_tache_rend_son_resultat_et_son_avancement() -> None:
    def calcul(annulation, avancer):
        for k in range(1, 4):
            avancer(Progression("etape", k, 3, f"unite {k}"))
        return 42

    tache = Tache(calcul, nom="essai").demarrer()
    assert tache.attendre(5)
    assert tache.etat is EtatTache.TERMINEE and tache.resultat() == 42
    assert tache.progression() == Progression("etape", 3, 3, "unite 3")
    assert [p.fraction for p in tache.evenements()] == pytest.approx([1 / 3, 2 / 3, 1.0])
    assert tache.evenements() == []


def test_un_echec_garde_l_erreur_et_la_trace_sans_la_perdre() -> None:
    def calcul(annulation, avancer):
        raise ValueError("motif de l'echec")

    tache = Tache(calcul).demarrer()
    tache.attendre(5)
    assert tache.etat is EtatTache.ECHEC and isinstance(tache.erreur, ValueError)
    assert "motif de l'echec" in tache.trace and "ValueError" in tache.trace
    with pytest.raises(ValueError, match="motif"):
        tache.resultat()


def test_l_annulation_arrete_le_calcul_entre_deux_unites() -> None:
    def calcul(annulation, avancer):
        for _ in range(1000):
            annulation.verifier()
            time.sleep(0.005)

    tache = Tache(calcul).demarrer()
    tache.annuler()
    assert tache.attendre(5)
    assert tache.etat is EtatTache.ANNULEE
    with pytest.raises(ErreurAnnulation):
        tache.resultat()


def test_une_tache_ne_se_lance_qu_une_fois_et_un_resultat_premature_est_refuse() -> None:
    tache = Tache(lambda annulation, avancer: None)
    with pytest.raises(RuntimeError, match="non terminée"):
        tache.resultat()
    tache.demarrer()
    tache.attendre(5)
    with pytest.raises(RuntimeError, match="déjà lancée"):
        tache.demarrer()


def test_la_fraction_d_un_total_inconnu_est_nulle_et_plafonnee_a_un() -> None:
    assert Progression("e", 3, 0).fraction == 0.0
    assert Progression("e", 9, 3).fraction == 1.0
