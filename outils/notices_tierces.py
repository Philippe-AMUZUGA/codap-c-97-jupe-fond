"""
Notices des dépendances : écrit l'inventaire de `THIRD_PARTY_NOTICES.md` d'après `requirements.txt`.

Usage, depuis la racine de l'application et avec l'environnement qui sert à la distribution :

    python outils/notices_tierces.py            réécrit le tableau de THIRD_PARTY_NOTICES.md
    python outils/notices_tierces.py -c         contrôle seulement : code 1 si le fichier n'est pas à jour
    python outils/notices_tierces.py -r AUTRE.txt -o AUTRE.md

Pour chaque exigence figée (`nom==version`), le script lit les métadonnées du paquet installé (licence, adresse du
projet) avec `importlib.metadata`. Il n'ouvre aucune connexion et n'installe rien. Un paquet absent de
l'environnement, ou dont la licence n'est pas déclarée, est écrit tel quel dans le tableau et fait rendre le code 2 :
il reste à examiner avant publication. Bibliothèque standard seule.

Codes : 0 inventaire complet, 1 fichier à mettre à jour (avec -c) ou entrée invalide, 2 paquet manquant ou sans licence.
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
from importlib import metadata
from pathlib import Path

DEBUT = "[//]: # (inventaire : début, ne pas modifier à la main)"
FIN = "[//]: # (inventaire : fin)"
ENTETE = ("Paquet", "Version", "Licence", "Adresse")
EXIGENCE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*==\s*([^\s;\\#]+)")


def normaliser(nom: str) -> str:
    """Nom de paquet comparable : minuscules, séparateurs ramenés au tiret bas."""
    return re.sub(r"[-_.]+", "-", nom).lower()


def lire_exigences(texte: str) -> list[tuple[str, str]]:
    """Couples (nom, version) des lignes `nom==version` ; commentaires, options et empreintes ignorés."""
    trouvees: list[tuple[str, str]] = []
    for ligne in texte.splitlines():
        brut = ligne.strip()
        if not brut or brut.startswith(("#", "-")):
            continue
        correspondance = EXIGENCE.match(brut)
        if correspondance:
            trouvees.append((correspondance.group(1), correspondance.group(2)))
    return trouvees


def licence_de(infos: metadata.PackageMetadata) -> str:
    """Licence déclarée : expression SPDX, sinon classifieurs, sinon première ligne courte du champ `License`."""
    expression = (infos.get("License-Expression") or "").strip()
    if expression:
        return expression
    classes = [c.split("::")[-1].strip() for c in (infos.get_all("Classifier") or []) if c.startswith("License ::")]
    classes = [c for c in classes if c and c.lower() != "osi approved"]
    if classes:
        return " ; ".join(dict.fromkeys(classes))
    champ = (infos.get("License") or "").strip()
    premiere = champ.splitlines()[0].strip() if champ else ""
    if premiere and len(premiere) <= 80 and premiere.upper() != "UNKNOWN":
        return premiere
    return ""


def adresse_de(infos: metadata.PackageMetadata) -> str:
    """Adresse officielle : `Home-page`, sinon une `Project-URL` (page d'accueil ou sources), sinon vide."""
    accueil = (infos.get("Home-page") or "").strip()
    if accueil:
        return accueil
    liens = {}
    for ligne in infos.get_all("Project-URL") or []:
        etiquette, _, lien = ligne.partition(",")
        liens[etiquette.strip().lower()] = lien.strip()
    for cle in ("homepage", "home", "source", "source code", "repository", "documentation"):
        if liens.get(cle):
            return liens[cle]
    return next(iter(liens.values()), "")


def releve(exigences: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Une ligne par dépendance, triée par nom ; `probleme` non vide quand le paquet manque ou n'a pas de licence."""
    lignes: list[dict[str, str]] = []
    for nom, version in exigences:
        ligne = {"paquet": nom, "version": version, "licence": "", "adresse": "", "probleme": ""}
        try:
            infos = metadata.metadata(nom)
            installee = metadata.version(nom)
        except metadata.PackageNotFoundError:
            ligne["licence"] = "non installé : licence à relever"
            ligne["probleme"] = "paquet absent de l'environnement"
        else:
            ligne["licence"] = licence_de(infos)
            ligne["adresse"] = adresse_de(infos)
            if installee != version:
                ligne["probleme"] = f"version installée {installee}, figée {version}"
            if not ligne["licence"]:
                ligne["licence"] = "non déclarée : à relever dans le paquet"
                ligne["probleme"] = ligne["probleme"] or "licence non déclarée"
        lignes.append(ligne)
    return sorted(lignes, key=lambda x: normaliser(x["paquet"]))


def cellule(texte: str) -> str:
    return texte.replace("|", "/").replace("\n", " ").strip() or "inconnue"


def tableau(lignes: list[dict[str, str]]) -> str:
    """Tableau Markdown de l'inventaire (une ligne d'en-tête, une ligne de filets, une ligne par paquet)."""
    sortie = ["| " + " | ".join(ENTETE) + " |", "|" + ":-|" * len(ENTETE)]
    for x in lignes:
        sortie.append(
            f"| {cellule(x['paquet'])} | {cellule(x['version'])} | {cellule(x['licence'])} | {cellule(x['adresse'])} |"
        )
    return "\n".join(sortie)


def remplacer_inventaire(document: str, bloc: str) -> str:
    """Remplace ce qui est entre les deux repères ; lève ValueError si l'un manque."""
    if DEBUT not in document or FIN not in document or document.index(DEBUT) > document.index(FIN):
        raise ValueError(f"repères « {DEBUT} » et « {FIN} » introuvables dans le fichier de notices")
    avant, _, reste = document.partition(DEBUT)
    _, _, apres = reste.partition(FIN)
    return f"{avant}{DEBUT}\n\n{bloc}\n\n{FIN}{apres}"


def analyseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description="Écrit l'inventaire des licences de THIRD_PARTY_NOTICES.md.", add_help=False
    )
    parseur.add_argument("-r", dest="requirements", default="requirements.txt", help="fichier des dépendances figées")
    parseur.add_argument(
        "-o", dest="sortie", default="THIRD_PARTY_NOTICES.md", help="fichier de notices à mettre à jour"
    )
    parseur.add_argument("-c", dest="controle", action="store_true", help="contrôle seulement, sans écrire")
    parseur.add_argument("-h", action="help", help="cette aide")
    return parseur


def sortie_en_utf8() -> None:
    """Messages en UTF-8 quelle que soit la page de code de la console ou du tube qui les lit."""
    for flux in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            flux.reconfigure(encoding="utf-8", errors="replace")


def principal(argv: list[str] | None = None) -> int:
    sortie_en_utf8()
    options = analyseur().parse_args(argv)
    requirements, sortie = Path(options.requirements), Path(options.sortie)
    if not requirements.is_file() or not sortie.is_file():
        print(f"Fichier introuvable : {requirements if not requirements.is_file() else sortie}", file=sys.stderr)
        return 1
    exigences = lire_exigences(requirements.read_text(encoding="utf-8"))
    if not exigences:
        print(f"Aucune dépendance figée (nom==version) dans {requirements}.", file=sys.stderr)
        return 1
    lignes = releve(exigences)
    try:
        nouveau = remplacer_inventaire(sortie.read_text(encoding="utf-8"), tableau(lignes))
    except ValueError as erreur:
        print(erreur, file=sys.stderr)
        return 1
    actuel = sortie.read_text(encoding="utf-8")
    if options.controle:
        if actuel.replace("\r\n", "\n") != nouveau:
            print(f"{sortie} n'est pas à jour : relancez outils/notices_tierces.py sans -c.")
            return 1
    else:
        sortie.write_bytes(nouveau.encode("utf-8"))
        print(f"{sortie} : {len(lignes)} dépendance(s) inventoriée(s).")
    problemes = [x for x in lignes if x["probleme"]]
    for x in problemes:
        print(f"À examiner : {x['paquet']} {x['version']} : {x['probleme']}.")
    return 2 if problemes else 0


if __name__ == "__main__":
    sys.exit(principal())
