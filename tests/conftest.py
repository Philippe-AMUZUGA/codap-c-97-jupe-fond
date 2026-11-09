"""Réglages communs : données de l'utilisateur isolées, langue remise à sa valeur, entrées de l'exemple."""

from __future__ import annotations

import json
import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from codap_c_97_jupe_fond import textes
from codap_c_97_jupe_fond.systeme import chemins, journal

RACINE = Path(__file__).resolve().parents[1]
PAQUET = RACINE / "src" / "codap_c_97_jupe_fond"
LANGUE_INITIALE = textes.langue()
NBSP = chr(0xA0)
CADRATIN = chr(0x2014)
DEMI_CADRATIN = chr(0x2013)
DOUBLE_TRAIT = chr(45) * 2


@pytest.fixture(autouse=True)
def donnees_isolees(tmp_path: Path) -> Iterator[None]:
    """Préférences et journaux vont sous le dossier temporaire du test : jamais dans les données réelles."""
    avant = chemins.redirection()
    log = logging.getLogger("codap_c_97_jupe_fond")
    propagation = log.propagate
    crochets = (sys.excepthook, threading.excepthook)
    chemins.rediriger(tmp_path / "donnees_app")
    yield
    journal.desinstaller()
    log.propagate = propagation
    chemins.rediriger(avant)
    sys.excepthook, threading.excepthook = crochets
    textes.definir_langue(LANGUE_INITIALE)


@pytest.fixture
def entrees_exemple() -> dict:
    """Valeurs brutes de `examples/exemple.json`."""
    return json.loads((RACINE / "examples" / "exemple.json").read_text(encoding="utf-8"))
