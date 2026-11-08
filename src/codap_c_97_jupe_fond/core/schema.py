"""
Schéma des entrées : ce que l'utilisateur saisit, avec type, unité, défaut, bornes, choix et aide.

Le schéma vient de `donnees/entrees.toml` (ou d'une signature de fonction, voir `champs_depuis_signature`).
Le formulaire de l'interface, la lecture d'un fichier d'entrées et la ligne de commande s'appuient tous sur
`valider` : une seule règle de validation, testée sans écran.

Une entrée peut être structurée : le type `tableau` porte des lignes dont les colonnes sont elles-mêmes des champs
(`[[entree.colonne]]` : nom, type, unité, bornes), avec un nombre de lignes borné (`lignes_min`, `lignes_max`).
Une liste de facteurs, de points de mesure ou de matériaux s'écrit ainsi, sans code propre à l'application. Une
entrée marquée `formulaire = false` est validée ici comme les autres mais saisie par un écran dédié, pas par le
formulaire généré.
"""

from __future__ import annotations

import inspect
import tomllib
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..textes import langue, lire_decimal, t
from .erreurs import ErreurSaisie

__all__ = [
    "TYPES",
    "TYPES_DE_COLONNE",
    "Champ",
    "champs_depuis_signature",
    "charger_schema",
    "valider",
    "valider_champ",
]

TYPES = ("reel", "entier", "texte", "choix", "booleen", "tableau")
TYPES_DE_COLONNE = ("reel", "entier", "texte", "choix", "booleen")
LONGUEUR_TEXTE_MAX = 200
LIGNES_MAX_PAR_DEFAUT = 1000
_VRAI = frozenset({"vrai", "oui", "true", "yes", "1", "on"})
_FAUX = frozenset({"faux", "non", "false", "no", "0", "off"})
_DOSSIER_DONNEES = Path(__file__).resolve().parents[1] / "donnees"


@dataclass(frozen=True)
class Champ:
    """Une entrée : nom du paramètre, type, défaut, bornes, choix, et textes par langue."""

    nom: str
    type: str
    defaut: Any = None
    unite: str = ""
    minimum: float | None = None
    maximum: float | None = None
    minimum_exclu: bool = False
    maximum_exclu: bool = False
    choix: tuple[str, ...] = ()
    libelle: Mapping[str, str] = field(default_factory=dict)
    aide: Mapping[str, str] = field(default_factory=dict)
    groupe: Mapping[str, str] = field(default_factory=dict)
    etiquettes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    colonnes: tuple[Champ, ...] = ()  # type `tableau` : un champ par colonne
    lignes_min: int = 0
    lignes_max: int = LIGNES_MAX_PAR_DEFAUT
    formulaire: bool = True  # faux : saisi par un écran dédié, validé ici comme les autres

    def libelle_dans(self, langue: str) -> str:
        """Libellé dans la langue, celui du français à défaut, le nom du paramètre en dernier recours."""
        return self.libelle.get(langue) or self.libelle.get("fr") or self.nom

    def aide_dans(self, langue: str) -> str:
        return self.aide.get(langue) or self.aide.get("fr") or ""

    def groupe_dans(self, langue: str) -> str:
        return self.groupe.get(langue) or self.groupe.get("fr") or ""

    def etiquette_dans(self, valeur: str, langue: str) -> str:
        """Texte affiché d'un choix ; la valeur elle-même s'il n'a pas d'étiquette."""
        table = self.etiquettes.get(valeur, {})
        return table.get(langue) or table.get("fr") or valeur


# ============================================================
# LECTURE DU SCHÉMA
# ============================================================
def _par_langue(table: Mapping[str, Any], base: str) -> dict[str, str]:
    """`base` et `base_en` d'un tableau TOML, rangés par code de langue."""
    textes = {}
    if base in table:
        textes["fr"] = str(table[base])
    if f"{base}_en" in table:
        textes["en"] = str(table[f"{base}_en"])
    return textes


def _etiquettes(table: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Étiquettes des choix : `etiquettes = {valeur = "Texte"}` et `etiquettes_en`."""
    rangees: dict[str, dict[str, str]] = {}
    for code, cle in (("fr", "etiquettes"), ("en", "etiquettes_en")):
        for valeur, texte in table.get(cle, {}).items():
            rangees.setdefault(str(valeur), {})[code] = str(texte)
    return rangees


def _champ(table: Mapping[str, Any], types: tuple[str, ...] = TYPES) -> Champ:
    nom = str(table["nom"])
    genre = str(table["type"])
    if genre not in types:
        raise ValueError(f"Entrée {nom} : type inconnu {genre!r} (attendu : {', '.join(types)}).")
    colonnes = tuple(_champ(c, TYPES_DE_COLONNE) for c in table.get("colonne", ())) if genre == "tableau" else ()
    champ = Champ(
        nom=nom,
        type=genre,
        defaut=table.get("defaut"),
        unite=str(table.get("unite", "")),
        minimum=table.get("minimum"),
        maximum=table.get("maximum"),
        minimum_exclu=bool(table.get("minimum_exclu", False)),
        maximum_exclu=bool(table.get("maximum_exclu", False)),
        choix=tuple(str(c) for c in table.get("choix", ())),
        libelle=_par_langue(table, "libelle"),
        aide=_par_langue(table, "aide"),
        groupe=_par_langue(table, "groupe"),
        etiquettes=_etiquettes(table),
        colonnes=colonnes,
        lignes_min=int(table.get("lignes_min", 0)),
        lignes_max=int(table.get("lignes_max", LIGNES_MAX_PAR_DEFAUT)),
        formulaire=bool(table.get("formulaire", True)),
    )
    if genre == "choix" and not champ.choix:
        raise ValueError(f"Entrée {nom} : un champ de type choix déclare ses valeurs (`choix`).")
    if genre == "tableau":
        _controler_tableau(champ)
    return champ


def _controler_tableau(champ: Champ) -> None:
    """Un tableau déclare au moins une colonne, des noms de colonnes uniques et des bornes de lignes cohérentes."""
    noms = [c.nom for c in champ.colonnes]
    if not noms:
        raise ValueError(f"Entrée {champ.nom} : un tableau déclare ses colonnes (`[[entree.colonne]]`).")
    if len(set(noms)) != len(noms):
        raise ValueError(f"Entrée {champ.nom} : le tableau répète un nom de colonne.")
    if not 0 <= champ.lignes_min <= champ.lignes_max:
        raise ValueError(f"Entrée {champ.nom} : lignes_min et lignes_max incohérents.")


def charger_schema(chemin: str | Path | None = None) -> tuple[Champ, ...]:
    """Champs de `donnees/entrees.toml` (ou du fichier indiqué), dans l'ordre du fichier."""
    source = Path(chemin) if chemin else _DOSSIER_DONNEES / "entrees.toml"
    table = tomllib.loads(source.read_text(encoding="utf-8"))
    champs = tuple(_champ(c) for c in table.get("entree", ()))
    noms = [c.nom for c in champs]
    if len(set(noms)) != len(noms):
        raise ValueError("Le schéma des entrées répète un nom de paramètre.")
    return champs


def champs_depuis_signature(
    fonction: Callable[..., Any],
    *,
    unites: Mapping[str, str] | None = None,
    bornes: Mapping[str, tuple[float | None, float | None]] | None = None,
) -> tuple[Champ, ...]:
    """Champs d'un formulaire lus dans la signature d'une fonction (annotations et valeurs par défaut).

    `float` donne un réel, `int` un entier, `bool` un booléen, `str` un texte, `Literal[...]` un choix.
    Aucune borne n'est inventée : elles viennent de `bornes` (minimum, maximum) ou restent absentes.
    Un paramètre sans valeur par défaut est obligatoire (`defaut` vaut None).
    """
    unites = unites or {}
    bornes = bornes or {}
    indices = typing.get_type_hints(fonction)
    champs = []
    for nom, parametre in inspect.signature(fonction).parameters.items():
        if parametre.kind in (parametre.VAR_POSITIONAL, parametre.VAR_KEYWORD):
            continue
        annotation = indices.get(nom, float if isinstance(parametre.default, float) else str)
        defaut = None if parametre.default is inspect.Parameter.empty else parametre.default
        choix: tuple[str, ...] = ()
        if typing.get_origin(annotation) is typing.Literal:
            genre, choix = "choix", tuple(str(v) for v in typing.get_args(annotation))
        elif annotation is bool:
            genre = "booleen"
        elif annotation is int:
            genre = "entier"
        elif annotation is float:
            genre = "reel"
        elif annotation is str:
            genre = "texte"
        else:
            raise ValueError(f"Paramètre {nom} : annotation {annotation!r} non prise en charge.")
        minimum, maximum = bornes.get(nom, (None, None))
        champs.append(
            Champ(
                nom=nom,
                type=genre,
                defaut=defaut,
                unite=unites.get(nom, ""),
                minimum=minimum,
                maximum=maximum,
                choix=choix,
                libelle={"fr": nom},
            )
        )
    return tuple(champs)


# ============================================================
# VALIDATION
# ============================================================
def _vide(valeur: Any) -> bool:
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _valeur_reelle(brut: Any) -> float:
    if isinstance(brut, bool):
        raise ValueError("booleen")
    if isinstance(brut, int | float):
        valeur = float(brut)
        if valeur != valeur or valeur in (float("inf"), float("-inf")):
            raise ValueError("fini")
        return valeur
    return lire_decimal(str(brut))


def _valeur_entiere(brut: Any) -> int:
    if isinstance(brut, bool):
        raise ValueError("booleen")
    if isinstance(brut, int):
        return brut
    valeur = _valeur_reelle(brut)
    if valeur != int(valeur):
        raise ValueError("entier")
    return int(valeur)


def _valeur_booleenne(brut: Any) -> bool:
    if isinstance(brut, bool):
        return brut
    texte = str(brut).strip().lower()
    if texte in _VRAI:
        return True
    if texte in _FAUX:
        return False
    raise ValueError("booleen")


def valider_champ(champ: Champ, brut: Any) -> Any:
    """Valeur typée d'une saisie, ou `ErreurSaisie` dont le message nomme le champ et dit le geste."""
    nom_champ = champ.libelle_dans(langue())
    if champ.type == "tableau":
        return _valider_tableau(champ, brut, nom_champ)
    if _vide(brut):
        if champ.type == "texte":
            return ""
        raise ErreurSaisie("saisie.vide", champ=nom_champ)
    try:
        if champ.type == "reel":
            valeur: Any = _valeur_reelle(brut)
        elif champ.type == "entier":
            valeur = _valeur_entiere(brut)
        elif champ.type == "booleen":
            valeur = _valeur_booleenne(brut)
        elif champ.type == "choix":
            valeur = str(brut).strip()
            if valeur not in champ.choix:
                raise ErreurSaisie("saisie.choix", champ=nom_champ, choix=", ".join(champ.choix))
        else:
            valeur = str(brut).strip()
            if len(valeur) > LONGUEUR_TEXTE_MAX or any(ord(c) < 32 for c in valeur):
                raise ErreurSaisie("saisie.texte", champ=nom_champ, maximum=LONGUEUR_TEXTE_MAX)
    except ValueError:
        genre = "saisie.entier" if champ.type == "entier" else "saisie.nombre"
        if champ.type == "booleen":
            genre = "saisie.booleen"
        raise ErreurSaisie(genre, champ=nom_champ) from None
    if champ.type in ("reel", "entier"):
        _verifier_bornes(champ, valeur, nom_champ)
    return valeur


def _valider_tableau(champ: Champ, brut: Any, nom: str) -> list[dict[str, Any]]:
    """Lignes typées d'un tableau : chaque ligne est une liste dans l'ordre des colonnes ou un objet nom vers valeur.

    Une colonne absente d'un objet prend son défaut. Le message d'une cellule refusée donne le numéro de la ligne
    (à partir de 1) et le message de la colonne.
    """
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        brut = []
    if not isinstance(brut, list | tuple):
        raise ErreurSaisie("saisie.tableau", champ=nom)
    if len(brut) < champ.lignes_min:
        raise ErreurSaisie("saisie.lignes_min", champ=nom, n=champ.lignes_min)
    if len(brut) > champ.lignes_max:
        raise ErreurSaisie("saisie.lignes_max", champ=nom, n=champ.lignes_max)
    noms = [c.nom for c in champ.colonnes]
    lignes: list[dict[str, Any]] = []
    for rang, ligne in enumerate(brut, start=1):
        if isinstance(ligne, Mapping) and set(ligne) <= set(noms):
            cellules = [ligne.get(c.nom, c.defaut) for c in champ.colonnes]
        elif isinstance(ligne, list | tuple) and len(ligne) == len(noms):
            cellules = list(ligne)
        else:
            raise ErreurSaisie("saisie.ligne_forme", champ=nom, ligne=rang, colonnes=", ".join(noms))
        valeurs: dict[str, Any] = {}
        for colonne, cellule in zip(champ.colonnes, cellules, strict=True):
            try:
                valeurs[colonne.nom] = valider_champ(colonne, cellule)
            except ErreurSaisie as erreur:
                raise ErreurSaisie("saisie.cellule", champ=nom, ligne=rang, detail=str(erreur)) from None
        lignes.append(valeurs)
    return lignes


def _verifier_bornes(champ: Champ, valeur: float, nom: str) -> None:
    unite = f" {champ.unite}" if champ.unite else ""
    if champ.minimum is not None and (valeur <= champ.minimum if champ.minimum_exclu else valeur < champ.minimum):
        cle = "saisie.minimum_exclu" if champ.minimum_exclu else "saisie.minimum"
        raise ErreurSaisie(cle, champ=nom, borne=f"{champ.minimum:g}{unite}")
    if champ.maximum is not None and (valeur >= champ.maximum if champ.maximum_exclu else valeur > champ.maximum):
        cle = "saisie.maximum_exclu" if champ.maximum_exclu else "saisie.maximum"
        raise ErreurSaisie(cle, champ=nom, borne=f"{champ.maximum:g}{unite}")


def valider(champs: tuple[Champ, ...], brut: Mapping[str, Any]) -> dict[str, Any]:
    """Valeurs typées et bornées de toutes les entrées ; un champ absent prend son défaut.

    Toutes les erreurs sont rassemblées : `ErreurSaisie.par_champ` donne le message de chaque champ en
    défaut, pour que l'interface les marque d'un coup. Un nom qui n'est pas dans le schéma est refusé.
    """
    connus = {c.nom for c in champs}
    erreurs: dict[str, str] = {}
    valeurs: dict[str, Any] = {}
    for nom in brut:
        if nom not in connus:
            erreurs[str(nom)] = t("saisie.inconnu", champ=nom)
    for champ in champs:
        saisi = brut.get(champ.nom, champ.defaut)
        try:
            valeurs[champ.nom] = valider_champ(champ, saisi)
        except ErreurSaisie as erreur:
            erreurs[champ.nom] = str(erreur)
    if erreurs:
        raise ErreurSaisie("saisie.plusieurs", par_champ=erreurs, n=len(erreurs), premier=next(iter(erreurs.values())))
    return valeurs
