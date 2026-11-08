"""
Boîtes de dialogue de la fenêtre, derrière une petite classe : on peut la remplacer sans écran ni clic.

`Dialogues` ouvre les vraies boîtes (fichiers, dossier, confirmation, information). `DialoguesAutomatiques`
répond d'avance, sans rien afficher : l'essai automatique (`-t`) et les tests de l'interface s'en servent, et
gardent la trace des questions posées pour vérifier ce que l'utilisateur aurait vu.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox

from ..textes import t

__all__ = ["GENRES", "Dialogues", "DialoguesAutomatiques", "types_de_fichiers"]

GENRES = ("json", "csv", "image", "xlsx")


def types_de_fichiers(genre: str) -> list[tuple[str, str]]:
    """Filtre des boîtes de fichiers : JSON (entrées, projet), csv (tableaux), classeur xlsx ou image (PNG puis SVG)."""
    if genre == "image":
        return [("PNG", "*.png"), ("SVG", "*.svg")]
    if genre == "csv":
        return [("CSV", "*.csv")]
    if genre == "xlsx":
        return [("Excel", "*.xlsx")]
    return [("JSON", "*.json")]


def _extension(genre: str) -> str:
    return {"image": ".png", "csv": ".csv", "xlsx": ".xlsx"}.get(genre, ".json")


class Dialogues:
    """Les vraies boîtes de dialogue du système."""

    def confirmer(self, texte: str) -> bool:
        return bool(messagebox.askokcancel(t("app.titre"), texte))

    def info(self, titre: str, texte: str) -> None:
        messagebox.showinfo(titre, texte)

    def ouvrir_fichier(self, titre: str, dossier: str = "", genre: str = "json") -> str:
        """Chemin d'un fichier à ouvrir (JSON par défaut), ou chaîne vide si l'utilisateur renonce."""
        return filedialog.askopenfilename(
            title=titre,
            initialdir=dossier or None,
            filetypes=[*types_de_fichiers(genre), (t("commun.tous"), "*.*")],
        )

    def enregistrer_fichier(self, titre: str, nom: str = "", dossier: str = "", genre: str = "json") -> str:
        """Chemin d'un fichier à écrire (JSON par défaut, image PNG ou SVG), ou chaîne vide si l'utilisateur renonce.

        La boîte du système demande elle-même avant de remplacer un fichier existant.
        """
        return filedialog.asksaveasfilename(
            title=titre,
            initialdir=dossier or None,
            initialfile=nom,
            defaultextension=_extension(genre),
            filetypes=types_de_fichiers(genre),
        )

    def choisir_dossier(self, titre: str, dossier: str = "") -> str:
        """Chemin d'un dossier, ou chaîne vide si l'utilisateur renonce."""
        return filedialog.askdirectory(title=titre, initialdir=dossier or None) or ""


class DialoguesAutomatiques(Dialogues):
    """Réponses d'avance, sans fenêtre ; `questions` garde ce qui a été demandé, dans l'ordre."""

    def __init__(self, *, confirmation: bool = True, fichier: str = "", dossier: str = "") -> None:
        self.confirmation = confirmation
        self.fichier = fichier
        self.dossier = dossier
        self.questions: list[tuple[str, str]] = []

    def confirmer(self, texte: str) -> bool:
        self.questions.append(("confirmer", texte))
        return self.confirmation

    def info(self, titre: str, texte: str) -> None:
        self.questions.append(("info", f"{titre} : {texte}"))

    def ouvrir_fichier(self, titre: str, dossier: str = "", genre: str = "json") -> str:
        self.questions.append(("ouvrir", titre))
        return self.fichier

    def enregistrer_fichier(self, titre: str, nom: str = "", dossier: str = "", genre: str = "json") -> str:
        self.questions.append(("enregistrer", titre))
        return self.fichier

    def choisir_dossier(self, titre: str, dossier: str = "") -> str:
        self.questions.append(("dossier", titre))
        return self.dossier
