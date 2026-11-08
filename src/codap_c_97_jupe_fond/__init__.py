"""CODAP C9.7 Jupe-Fond.

Ce fichier est la source unique de la version et des constantes d'identité de l'application.
"""

from __future__ import annotations

__all__ = [
    "ANNEE",
    "AUTEUR",
    "COMPTE_GITHUB",
    "COURRIEL",
    "DESCRIPTION",
    "LICENCE",
    "NOM",
    "PYTHON_MAX",
    "PYTHON_MIN",
    "SLUG",
    "SLUG_MIN",
    "URL_DEPOT",
    "URL_RELEASES",
    "__version__",
]

__version__ = "0.1.0"

NOM = "CODAP C9.7 Jupe-Fond"
DESCRIPTION = "Vérification CODAP C9.7.5 des assemblages jupe-fond et comparaison à une référence EF"
SLUG = "CodapC97JupeFond"
SLUG_MIN = "codap-c-97-jupe-fond"
AUTEUR = "Philippe Amuzuga"
LICENCE = "MIT"
ANNEE = "2026"
COMPTE_GITHUB = "Philippe-AMUZUGA"
COURRIEL = "Philippe-AMUZUGA@users.noreply.github.com"

# Plage de Python acceptée : une seule source, `requires-python` de pyproject.toml, que test_coherence relit.
PYTHON_MIN = "3.11"
PYTHON_MAX = "3.13"

URL_DEPOT = f"https://github.com/{COMPTE_GITHUB}/{SLUG_MIN}"
URL_RELEASES = f"{URL_DEPOT}/releases"
