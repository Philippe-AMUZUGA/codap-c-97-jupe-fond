"""
Textes de l'interface, rangés par clés dans `interface_fr.toml` et `interface_en.toml`.

Le code n'écrit aucune phrase en dur : il demande un texte par sa clé (`t("menu.fichier")`). Un texte peut
contenir des champs `{nom}` remplis par les arguments de `t`. En français, l'espace insécable est posée à la
lecture avant « : ; ! ? » et à l'intérieur des guillemets, pour que le fichier reste simple à relire. Les
nombres suivent la langue : virgule décimale en français, point en anglais ; la saisie accepte les deux.
"""

from __future__ import annotations

import re
import string
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "LANGUES",
    "champs_de",
    "cles",
    "definir_langue",
    "existe",
    "formater_nombre",
    "langue",
    "lire_decimal",
    "t",
    "t_sortie",
]

_DOSSIER = Path(__file__).resolve().parent
#: Langues livrées : une langue existe quand son fichier `interface_<code>.toml` est présent (anglais : niveau 2).
LANGUES = tuple(code for code in ("fr", "en") if (_DOSSIER / f"interface_{code}.toml").is_file())
LANGUE_PAR_DEFAUT = "fr"

_INSECABLE = chr(0xA0)  # espace insécable
_AVANT_PONCTUATION = re.compile(r" ([:;!?»])")
_FORME_NOMBRE = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
_langue = LANGUE_PAR_DEFAUT if LANGUE_PAR_DEFAUT in LANGUES else "fr"


def langue() -> str:
    """Code de la langue courante (`fr` ou `en`)."""
    return _langue


def definir_langue(code: str) -> str:
    """Choisit la langue des textes ; une langue inconnue est refusée. Rend le code retenu."""
    global _langue
    if code not in LANGUES:
        raise ValueError(f"Langue inconnue : {code!r} (attendu : {', '.join(LANGUES)}).")
    _langue = code
    return _langue


def _normaliser(texte: str, code: str) -> str:
    """Espaces insécables de la typographie française ; l'anglais est laissé tel quel."""
    if code != "fr":
        return texte
    texte = _AVANT_PONCTUATION.sub(_INSECABLE + r"\1", texte)
    return texte.replace("« ", "«" + _INSECABLE)


def _aplatir(table: dict[str, Any], code: str, prefixe: str = "") -> dict[str, str]:
    plat: dict[str, str] = {}
    for nom, valeur in table.items():
        cle = f"{prefixe}{nom}"
        if isinstance(valeur, dict):
            plat.update(_aplatir(valeur, code, f"{cle}."))
        else:
            plat[cle] = _normaliser(str(valeur), code)
    return plat


@lru_cache(maxsize=len(LANGUES))
def _textes(code: str) -> dict[str, str]:
    source = (_DOSSIER / f"interface_{code}.toml").read_text(encoding="utf-8")
    return _aplatir(tomllib.loads(source), code)


def cles(code: str | None = None) -> frozenset[str]:
    """Toutes les clés de texte d'une langue (la langue courante par défaut)."""
    return frozenset(_textes(code or _langue))


def existe(cle: str, code: str | None = None) -> bool:
    """Vrai si la clé a un texte dans la langue."""
    return cle in _textes(code or _langue)


def t(cle: str, **valeurs: Any) -> str:
    """Texte de la clé, champs remplis ; `KeyError` explicite si la clé manque."""
    try:
        texte = _textes(_langue)[cle]
    except KeyError:
        raise KeyError(f"Clé de texte absente de interface_{_langue}.toml : {cle!r}.") from None
    return texte.format(**valeurs) if valeurs else texte


def t_sortie(cle: str) -> str:
    """Libellé d'une sortie (`sortie.<cle>`) ; à défaut, la clé rendue lisible (sortie connue à l'exécution)."""
    if existe(f"sortie.{cle}"):
        return t(f"sortie.{cle}")
    return cle.replace("_", " ").strip().capitalize() or cle


def champs_de(texte: str) -> frozenset[str]:
    """Noms des champs `{nom}` d'un texte (pour contrôler la parité des deux langues)."""
    return frozenset(nom for _, nom, _, _ in string.Formatter().parse(texte) if nom)


def formater_nombre(valeur: float, chiffres: int | None = None) -> str:
    """Nombre selon la langue : virgule décimale en français, point en anglais.

    Sans `chiffres`, la forme la plus courte qui relit la même valeur (10 chiffres significatifs).
    """
    texte = f"{valeur:.10g}" if chiffres is None else f"{valeur:.{chiffres}f}"
    return texte.replace(".", ",") if _langue == "fr" else texte


def lire_decimal(texte: str) -> float:
    """Nombre saisi avec une virgule ou un point décimal ; `ValueError` si le texte n'est pas un nombre.

    Les espaces (y compris insécables) séparant les milliers sont ignorés ; un texte qui mêle virgule et
    point est refusé, faute de pouvoir dire lequel est le séparateur décimal.
    """
    nettoye = re.sub(r"[\s" + _INSECABLE + chr(0x202F) + "]", "", str(texte))
    if "," in nettoye and "." in nettoye:
        raise ValueError(f"Nombre ambigu : {texte!r}.")
    nettoye = nettoye.replace(",", ".")
    if not _FORME_NOMBRE.fullmatch(nettoye):
        raise ValueError(f"Nombre attendu : {texte!r}.")
    valeur = float(nettoye)
    if valeur in (float("inf"), float("-inf")):
        raise ValueError(f"Nombre fini attendu : {texte!r}.")
    return valeur
