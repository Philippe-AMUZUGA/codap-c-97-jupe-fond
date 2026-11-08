"""Essai automatique (-t), ligne de commande et point d'entrée : options courtes, code de sortie, aucune connexion."""

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest

from codap_c_97_jupe_fond import __main__ as principal
from codap_c_97_jupe_fond import cli, essai
from codap_c_97_jupe_fond.systeme import chemins


def test_les_options_sont_courtes_et_sans_double_trait_d_union() -> None:
    for analyseur in (principal._analyseur(), cli._analyseur()):
        options = [s for action in analyseur._actions for s in action.option_strings]
        assert options and all(len(s) == 2 and s[0] == "-" and s[1].isalpha() for s in options), options
    assert {"-t", "-s", "-v", "-V", "-h"} <= {s for a in principal._analyseur()._actions for s in a.option_strings}


def test_le_poste_est_pret_et_le_numero_de_version_s_affiche(capsys: pytest.CaptureFixture) -> None:
    assert principal.verifier_poste() is None and principal.modules_manquants() == []
    with pytest.raises(SystemExit) as sortie:
        principal.principal(["-V"])
    assert sortie.value.code == 0
    assert "." in capsys.readouterr().out


def test_les_connexions_sont_refusees_et_comptees() -> None:
    originale = socket.create_connection
    with essai.bloquer_reseau() as tentatives:
        with pytest.raises(OSError, match="refusée"):
            socket.create_connection(("exemple.invalid", 80))
        with pytest.raises(OSError, match="refusée"):
            socket.getaddrinfo("exemple.invalid", 80)
    assert len(tentatives) == 2
    assert socket.create_connection is originale


def test_l_essai_automatique_reussit_en_moins_d_une_minute(tmp_path: Path) -> None:
    lignes: list[str] = []
    sortie = tmp_path / "sortie_essai"
    redirection = chemins.redirection()
    debut = time.monotonic()
    code = essai.essai_automatique(str(sortie), lignes.append)
    duree = time.monotonic() - debut
    assert code == 0, "\n".join(lignes)
    assert duree < 60, f"{duree:.0f} s"
    etapes = [ligne for ligne in lignes if ligne.startswith("[")]
    assert [e[:5] for e in etapes] == [f"[{k}/7]" for k in range(1, 8)]
    assert all("échec" not in e for e in etapes)
    assert any("export" in e and "réussi" in e for e in etapes)
    interface = etapes[-1]
    assert "ignoré" in interface or ("tâche(s) d'étape" in interface and "image(s)" in interface), interface
    assert sum(p.is_file() for p in sortie.rglob("*")) >= 5, "l'essai doit exporter au moins un fichier"
    assert chemins.redirection() == redirection, "l'essai remet les chemins comme il les a trouvés"
