"""
Export d'un résultat : classeur xlsx, fichiers csv, figures png et `projet.json` à empreintes.

Tout est écrit dans le seul dossier choisi par l'utilisateur : un nom absolu, un `..`, un nom réservé de
Windows ou un lien qui sortirait du dossier est refusé. Un fichier existant n'est jamais écrasé sans que
l'appelant l'ait demandé (`ecraser=True`, après confirmation). Chaque fichier est écrit sous un nom
provisoire puis posé d'un coup, pour qu'une interruption ne laisse pas un fichier tronqué.
`projet.json` consigne les entrées, les mesures et l'empreinte SHA-256 des autres fichiers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .. import SLUG, __version__
from ..textes import formater_nombre, langue, t, t_sortie
from .erreurs import ErreurExport
from .resultat import Resultat
from .taches import Annulation

__all__ = [
    "FORMATS",
    "FORMAT_PROJET",
    "chemin_dans_dossier",
    "empreinte_fichier",
    "enregistrer_figure",
    "exporter",
    "fichiers_a_ecrire",
    "fichiers_existants",
]

FORMATS = ("xlsx", "csv", "png", "json")
FORMATS_IMAGE = ("png", "svg")  # une figure enregistrée seule, par le dialogue de l'interface
FORMAT_PROJET = 1
NOM_PROJET = "projet.json"
_CARACTERES_INTERDITS = re.compile(r'[<>:"|?*\x00-\x1f]')
_NOMS_RESERVES = frozenset(
    {"con", "prn", "aux", "nul", *(f"com{k}" for k in range(1, 10)), *(f"lpt{k}" for k in range(1, 10))}
)
_DEBUT_FORMULE = ("=", "+", "-", "@")


def chemin_dans_dossier(dossier: str | Path, nom: str) -> Path:
    """Chemin d'un fichier à écrire, garanti sous `dossier` (le dossier choisi par l'utilisateur)."""
    if not isinstance(nom, str) or not nom.strip():
        raise ErreurExport("export.nom_vide")
    win, posix = PureWindowsPath(nom), PurePosixPath(nom)
    if win.anchor or posix.is_absolute() or ".." in win.parts or ".." in posix.parts:
        raise ErreurExport("export.nom_sort", nom=nom)
    if _CARACTERES_INTERDITS.search(nom):
        raise ErreurExport("export.nom_interdit", nom=nom)
    for partie in win.parts:
        if partie.rstrip(". ") != partie or partie.split(".")[0].lower() in _NOMS_RESERVES:
            raise ErreurExport("export.nom_reserve", nom=nom)
    base = Path(dossier)
    if not base.is_dir():
        raise ErreurExport("export.dossier_absent", dossier=str(base))
    base = base.resolve()
    cible = (base / nom).resolve()
    if cible != base and base not in cible.parents:
        raise ErreurExport("export.nom_sort", nom=nom)
    return cible


def empreinte_fichier(chemin: str | Path) -> str:
    """Empreinte SHA-256 d'un fichier, en hexadécimal."""
    resume = hashlib.sha256()
    with open(chemin, "rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            resume.update(bloc)
    return resume.hexdigest()


def _nom_sur(texte: str) -> str:
    """Partie d'un nom de fichier tirée d'un texte : lettres, chiffres, point, tiret bas ; jamais vide."""
    propre = re.sub(r"[^\w.]+", "_", texte, flags=re.ASCII).strip("._")
    return propre[:60] or "resultats"


def fichiers_a_ecrire(resultat: Resultat, nom: str, formats: Iterable[str]) -> list[str]:
    """Noms des fichiers qu'un export écrirait, `projet.json` compris (pour prévenir d'un écrasement)."""
    base = _nom_sur(nom)
    formats = set(formats)
    noms = []
    if "xlsx" in formats:
        noms.append(f"{base}.xlsx")
    if "csv" in formats:
        noms.append(f"{base}_mesures.csv")
        noms += [f"{base}_{tableau.cle}.csv" for tableau in resultat.tableaux]
    if "png" in formats:
        noms += [f"{base}_figure{k}.png" for k in range(1, len(resultat.figures) + 1)]
    if "json" in formats:
        noms.append(NOM_PROJET)
    return noms


def fichiers_existants(resultat: Resultat, dossier: str | Path, nom: str, formats: Iterable[str]) -> list[str]:
    """Parmi les fichiers qu'un export écrirait, ceux qui existent déjà dans le dossier."""
    return [n for n in fichiers_a_ecrire(resultat, nom, formats) if chemin_dans_dossier(dossier, n).exists()]


def _texte_sur(valeur: Any) -> Any:
    """Valeur écrite dans un tableur ou un csv : un texte qui commencerait comme une formule est neutralisé."""
    if isinstance(valeur, str) and valeur.startswith(_DEBUT_FORMULE):
        return "'" + valeur
    return valeur


def _poser(ecrire: Callable[[Path], None], cible: Path) -> None:
    """Écrit sous un nom provisoire puis pose le fichier d'un coup."""
    provisoire = cible.with_name(cible.name + ".tmp")
    try:
        ecrire(provisoire)
        os.replace(provisoire, cible)
    finally:
        provisoire.unlink(missing_ok=True)


def _cellule(valeur: Any) -> str:
    if isinstance(valeur, float):
        return formater_nombre(valeur)
    return "" if valeur is None else str(_texte_sur(valeur))


def _ecrire_csv(chemin: Path, entetes: Sequence[str], lignes: Iterable[Sequence[Any]]) -> None:
    with open(chemin, "w", encoding="utf-8-sig", newline="") as flux:
        auteur = csv.writer(flux, delimiter=";" if langue() == "fr" else ",")
        auteur.writerow(entetes)
        for ligne in lignes:
            auteur.writerow([_cellule(v) for v in ligne])


def _ecrire_xlsx(chemin: Path, resultat: Resultat, titre: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = t("export.feuille_mesures")
    gras = Font(bold=True)
    for colonne, cle in enumerate(("export.col_mesure", "export.col_valeur", "export.col_unite"), start=1):
        feuille.cell(row=1, column=colonne, value=t(cle)).font = gras
    for rang, mesure in enumerate(resultat.mesures, start=2):
        feuille.cell(row=rang, column=1, value=t_sortie(mesure.cle))
        _poser_cellule(feuille.cell(row=rang, column=2), mesure.valeur)
        feuille.cell(row=rang, column=3, value=mesure.unite)
    feuille.column_dimensions["A"].width = 34
    feuille.column_dimensions["B"].width = 18
    for tableau in resultat.tableaux:
        page = classeur.create_sheet(title=t_sortie(tableau.cle)[:31])
        for colonne, cle in enumerate(tableau.colonnes, start=1):
            page.cell(row=1, column=colonne, value=t_sortie(cle)).font = gras
            page.column_dimensions[page.cell(row=1, column=colonne).column_letter].width = 22
        for rang, ligne in enumerate(tableau.lignes, start=2):
            for colonne, valeur in enumerate(ligne, start=1):
                _poser_cellule(page.cell(row=rang, column=colonne), valeur)
    classeur.properties.title = titre
    classeur.properties.creator = SLUG
    classeur.save(chemin)


def _poser_cellule(cellule: Any, valeur: Any) -> None:
    """Pose une valeur ; un texte reste un texte, même s'il commence par « = »."""
    cellule.value = valeur
    if isinstance(valeur, str):
        cellule.data_type = "s"


def _ecrire_png(chemin: Path, figure: Any) -> None:
    figure.savefig(chemin, format="png", dpi=150)


def enregistrer_figure(figure: Any, chemin: str | Path) -> Path:
    """Écrit une figure dans le fichier choisi par l'utilisateur, en PNG ou en SVG selon son extension.

    Sans extension, le fichier est un PNG ; une autre extension est refusée. Le dossier doit exister. L'écriture
    passe par un nom provisoire puis pose le fichier d'un coup (le dialogue a déjà demandé avant d'écraser).
    """
    cible = Path(chemin)
    if not cible.suffix:
        cible = cible.with_suffix(".png")
    genre = cible.suffix.lower().lstrip(".")
    if genre not in FORMATS_IMAGE:
        raise ErreurExport("image.format", format=cible.suffix, formats=", ".join(FORMATS_IMAGE))
    if not cible.parent.is_dir():
        raise ErreurExport("export.dossier_absent", dossier=str(cible.parent))
    _poser(lambda p: figure.savefig(p, format=genre, dpi=150), cible)
    return cible


def exporter(
    resultat: Resultat,
    dossier: str | Path,
    *,
    nom: str = "resultats",
    formats: Sequence[str] = FORMATS,
    ecraser: bool = False,
    annulation: Annulation | None = None,
) -> list[Path]:
    """Écrit les sorties demandées dans `dossier` ; rend les chemins écrits.

    Refuse un format inconnu et, sans `ecraser`, un fichier déjà présent (rien n'est alors écrit).
    """
    annulation = annulation or Annulation()
    inconnus = [f for f in formats if f not in FORMATS]
    if inconnus:
        raise ErreurExport("export.format_inconnu", format=", ".join(inconnus))
    if not formats:
        raise ErreurExport("export.aucun_format")
    base = _nom_sur(nom)
    prevus = {n: chemin_dans_dossier(dossier, n) for n in fichiers_a_ecrire(resultat, nom, formats)}
    presents = [n for n, chemin in prevus.items() if chemin.exists()]
    if presents and not ecraser:
        raise ErreurExport("export.existe", noms=", ".join(presents))
    ecrits: list[Path] = []

    def ecrire(nom_fichier: str, fabrique: Callable[[Path], None]) -> None:
        annulation.verifier()
        _poser(fabrique, prevus[nom_fichier])
        ecrits.append(prevus[nom_fichier])

    if "xlsx" in formats:
        ecrire(f"{base}.xlsx", lambda p: _ecrire_xlsx(p, resultat, nom))
    if "csv" in formats:
        mesures = [(t_sortie(m.cle), m.valeur, m.unite) for m in resultat.mesures]
        ecrire(
            f"{base}_mesures.csv",
            lambda p: _ecrire_csv(p, (t("export.col_mesure"), t("export.col_valeur"), t("export.col_unite")), mesures),
        )
        for tableau in resultat.tableaux:
            entetes = [t_sortie(c) for c in tableau.colonnes]
            ecrire(f"{base}_{tableau.cle}.csv", lambda p, e=entetes, x=tableau.lignes: _ecrire_csv(p, e, x))
    if "png" in formats:
        for k, figure in enumerate(resultat.figures, start=1):
            ecrire(f"{base}_figure{k}.png", lambda p, f=figure: _ecrire_png(p, f))
    if "json" in formats:
        annulation.verifier()
        _poser(lambda p: _ecrire_projet(p, resultat, nom, ecrits), prevus[NOM_PROJET])
        ecrits.append(prevus[NOM_PROJET])
    return ecrits


def _ecrire_projet(chemin: Path, resultat: Resultat, nom: str, fichiers: Sequence[Path]) -> None:
    contenu = {
        "version_format": FORMAT_PROJET,
        "application": SLUG,
        "version": __version__,
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nom": nom,
        "entrees": resultat.entrees,
        "mesures": {m.cle: {"valeur": _json_sur(m.valeur), "unite": m.unite} for m in resultat.mesures},
        "fichiers": {f.name: empreinte_fichier(f) for f in fichiers},
    }
    texte = json.dumps(contenu, ensure_ascii=False, indent=2, allow_nan=False)
    chemin.write_text(texte + "\n", encoding="utf-8")


def _json_sur(valeur: Any) -> Any:
    """Un nombre non fini n'existe pas en JSON : il devient `null`."""
    if isinstance(valeur, float) and not math.isfinite(valeur):
        return None
    return valeur
