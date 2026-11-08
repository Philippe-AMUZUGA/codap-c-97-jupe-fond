"""Ligne de commande : calcul depuis un fichier d'entrées, export, rejeu d'un projet, refus d'un fichier invalide.

Les attentes se déduisent du calcul et du schéma de l'application : le même test vaut pour toute application.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codap_c_97_jupe_fond import cli
from codap_c_97_jupe_fond.core import calculs, export
from codap_c_97_jupe_fond.core.schema import charger_schema, valider
from codap_c_97_jupe_fond.textes import formater_nombre, t_sortie

EXEMPLE = Path(__file__).resolve().parents[1] / "examples" / "exemple.json"


def _ligne_attendue(mesure) -> str:
    valeur = formater_nombre(mesure.valeur, 4) if isinstance(mesure.valeur, float) else str(mesure.valeur)
    return f"{t_sortie(mesure.cle)} : {valeur} {mesure.unite}".rstrip()


def test_la_ligne_de_commande_calcule_et_exporte(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    sortie = tmp_path / "sortie"
    sortie.mkdir()
    code = cli.principal([str(EXEMPLE), "-o", str(sortie), "-f", "csv,json", "-n", "cli", "-l", "fr"])
    affichage = capsys.readouterr().out
    resultat = calculs.calculer(valider(charger_schema(), json.loads(EXEMPLE.read_text(encoding="utf-8"))))
    assert code == 0
    for mesure in resultat.mesures:
        assert _ligne_attendue(mesure) in affichage, mesure.cle
    attendus = sorted(export.fichiers_a_ecrire(resultat, "cli", ("csv", "json")))
    assert sorted(p.name for p in sortie.iterdir()) == attendus
    # un export se rejoue : le projet.json se relit comme un fichier d'entrées
    assert cli.principal([str(sortie / "projet.json")]) == 0
    assert _ligne_attendue(resultat.mesures[0]) in capsys.readouterr().out
    # sans -e, un fichier existant est refusé ; avec -e, remplacé
    assert cli.principal([str(EXEMPLE), "-o", str(sortie), "-f", "csv", "-n", "cli"]) == 1
    assert "existent déjà" in capsys.readouterr().err
    assert cli.principal([str(EXEMPLE), "-o", str(sortie), "-f", "csv", "-n", "cli", "-e"]) == 0


def test_la_ligne_de_commande_refuse_un_fichier_invalide(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    invalides = {"reel": "abc", "entier": "abc", "choix": "valeur_inconnue", "booleen": "peut-etre", "texte": "x" * 300}
    champ = charger_schema()[0]
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text(json.dumps({champ.nom: invalides[champ.type], "inconnue": 1}), encoding="utf-8")
    assert cli.principal([str(mauvais), "-l", "fr"]) == 1
    erreurs = capsys.readouterr().err
    assert champ.libelle_dans("fr") in erreurs and "inconnue" in erreurs, "toutes les entrées en défaut sont dites"
    mauvais.write_text("pas du json", encoding="utf-8")
    assert cli.principal([str(mauvais)]) == 1
    assert "JSON" in capsys.readouterr().err
    assert cli.principal([str(tmp_path / "absent.json")]) == 1
