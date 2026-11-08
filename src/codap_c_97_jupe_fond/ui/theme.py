"""
Thème de l'interface : palettes claire et sombre, polices de repli, taille réglable, styles ttk.

Le style est celui des applications de bureau de l'auteur : fond gris bleuté, cartes à filet fin, accent bleu
acier, thème ttk « clam ». La palette claire est la palette d'origine ; la palette sombre a ses contrastes
mesurés par `contraste` (formule WCAG 2) et contrôlés par `tests/test_theme.py` : 4,5 au moins pour un texte,
3 pour un élément d'interface (l'accent sur une carte compris), hors boutons désactivés. Les polices passent par
des polices nommées de Tk, jamais par l'option `*Font`, qui écraserait les styles ; changer la taille revient à
reconfigurer ces polices. Les figures du noyau sont dessinées aux couleurs de la charte claire : `figure_au_theme`
en donne, pour l'affichage en thème sombre, une copie aux couleurs de la palette sombre (l'original sert aux exports).
"""

from __future__ import annotations

import contextlib
import copy
import tkinter as tk
from collections.abc import Iterable
from dataclasses import dataclass, fields
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

__all__ = [
    "PALETTES",
    "TAILLE_NORMALE",
    "Palette",
    "appliquer",
    "choisir_famille",
    "contraste",
    "couleurs",
    "figure_au_theme",
    "habiller_figure",
    "luminance",
    "recolorier",
    "taille_police",
]

TAILLE_NORMALE = 100
FAMILLES_CORPS = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial")
FAMILLES_MONO = ("Consolas", "Menlo", "DejaVu Sans Mono", "Liberation Mono", "Courier New")
FAMILLE_GRAS = "Segoe UI Semibold"

# Corps 10, titre d'écran 20, carte 11, ligne de tableau 26 pixels : valeurs de l'application de référence.
TAILLES_DE_BASE = {"AppCorps": 10, "AppGras": 10, "AppCarte": 11, "AppTitre": 20, "AppSous": 11, "AppMono": 10}
HAUTEUR_LIGNE = 26


@dataclass(frozen=True)
class Palette:
    """Couleurs d'un thème (valeurs hexadécimales)."""

    fond: str
    carte: str
    texte: str
    doux: str
    accent: str
    accent_appui: str
    sur_accent: str
    lien: str
    rouge: str
    orange: str
    vert: str
    bordure: str
    entete: str
    selection: str
    texte_selection: str
    inactif: str
    sur_inactif: str


PALETTES = {
    "clair": Palette(
        fond="#EEF2F7", carte="#FFFFFF", texte="#18212F", doux="#5C6778", accent="#335C81",
        accent_appui="#264A68", sur_accent="#FFFFFF", lien="#335C81", rouge="#B3261E", orange="#9A5B00",
        vert="#2E7D32", bordure="#D6DDE6", entete="#E8EEF5", selection="#CFE0F0", texte_selection="#18212F",
        inactif="#9DB2C5", sur_inactif="#F2F5F8",
    ),
    "sombre": Palette(
        fond="#151B23", carte="#1E2630", texte="#E6EBF2", doux="#A3AFBD", accent="#4175A3",
        accent_appui="#2E5B83", sur_accent="#FFFFFF", lien="#8DB8E0", rouge="#F2A7A2", orange="#E8B66A",
        vert="#86CF8A", bordure="#364252", entete="#26313E", selection="#2F4A66", texte_selection="#E6EBF2",
        inactif="#3A4756", sur_inactif="#8794A3",
    ),
}  # fmt: skip

_courante = PALETTES["clair"]


def couleurs() -> Palette:
    """Palette du thème appliqué en dernier."""
    return _courante


def luminance(couleur: str) -> float:
    """Luminance relative d'une couleur `#RRGGBB` (WCAG 2)."""
    composantes = []
    for k in (1, 3, 5):
        c = int(couleur[k : k + 2], 16) / 255
        composantes.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * composantes[0] + 0.7152 * composantes[1] + 0.0722 * composantes[2]


def contraste(premiere: str, seconde: str) -> float:
    """Rapport de contraste de deux couleurs (de 1 à 21)."""
    a, b = sorted((luminance(premiere), luminance(seconde)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def choisir_famille(souhaitees: Iterable[str], existantes: Iterable[str], repli: str = "TkDefaultFont") -> str:
    """Première famille souhaitée que le système possède (sans tenir compte de la casse), sinon le repli."""
    presentes = {nom.lower(): nom for nom in existantes}
    for nom in souhaitees:
        if nom.lower() in presentes:
            return presentes[nom.lower()]
    return repli


def taille_police(base: int, pourcentage: int) -> int:
    """Taille en points d'une police de base à l'échelle choisie (7 points au moins)."""
    return max(7, round(base * pourcentage / 100))


def appliquer(racine: tk.Misc, theme: str = "clair", pourcentage: int = TAILLE_NORMALE) -> ttk.Style:
    """Installe le thème sur la fenêtre (palette, polices, styles) et rend le style configuré."""
    global _courante
    _courante = PALETTES.get(theme, PALETTES["clair"])
    style = ttk.Style(racine)
    with contextlib.suppress(tk.TclError):
        style.theme_use("clam")
    _polices(racine, pourcentage)
    racine.configure(background=_courante.fond)
    _options(racine)
    _cadres(style)
    _boutons(style)
    _tableaux(style, pourcentage)
    _champs(style)
    return style


def _police_nommee(racine: tk.Misc, nom: str, **options: object) -> tkfont.Font:
    """Crée ou reconfigure une police nommée de Tk.

    Un objet `Font` supprime sa police nommée quand Python le libère : `delete_font` est donc coupé, la police
    vit autant que l'interpréteur Tk (la fenêtre), et les styles qui la citent par son nom la retrouvent.
    """
    try:
        police = tkfont.nametofont(nom, root=racine)
        police.configure(**options)
    except tk.TclError:
        police = tkfont.Font(root=racine, name=nom, exists=False, **options)
    police.delete_font = False
    return police


def _polices(racine: tk.Misc, pourcentage: int) -> None:
    existantes = set(tkfont.families(root=racine))
    corps = choisir_famille(FAMILLES_CORPS, existantes)
    mono = choisir_famille(FAMILLES_MONO, existantes, repli="TkFixedFont")
    semi = FAMILLE_GRAS if FAMILLE_GRAS in existantes else corps
    gras = "normal" if semi == FAMILLE_GRAS else "bold"
    for nom, base in TAILLES_DE_BASE.items():
        taille = taille_police(base, pourcentage)
        if nom == "AppMono":
            _police_nommee(racine, nom, family=mono, size=taille)
        elif nom in ("AppGras", "AppCarte", "AppTitre"):
            _police_nommee(racine, nom, family=semi, size=taille, weight=gras)
        else:
            _police_nommee(racine, nom, family=corps, size=taille)
    for nom in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkIconFont", "TkTooltipFont"):
        with contextlib.suppress(tk.TclError):
            tkfont.nametofont(nom, root=racine).configure(family=corps, size=taille_police(10, pourcentage))


def _options(racine: tk.Misc) -> None:
    """Options des composants Tk classiques (liste déroulante, menus, texte) pour le thème courant."""
    p = _courante
    for motif, valeur in (
        ("*TCombobox*Listbox.font", "AppCorps"),
        ("*TCombobox*Listbox.background", p.carte),
        ("*TCombobox*Listbox.foreground", p.texte),
        ("*TCombobox*Listbox.selectBackground", p.selection),
        ("*TCombobox*Listbox.selectForeground", p.texte_selection),
    ):
        racine.option_add(motif, valeur)


def _cadres(style: ttk.Style) -> None:
    p = _courante
    style.configure("TFrame", background=p.fond)
    style.configure("Carte.TFrame", background=p.carte)
    style.configure("TLabel", background=p.fond, foreground=p.texte, font="AppCorps")
    style.configure("Doux.TLabel", background=p.fond, foreground=p.doux, font="AppCorps")
    style.configure("Titre.TLabel", background=p.fond, foreground=p.texte, font="AppTitre")
    style.configure("Sous.TLabel", background=p.fond, foreground=p.doux, font="AppSous")
    style.configure("Carte.TLabel", background=p.carte, foreground=p.texte, font="AppCorps")
    style.configure("CarteDoux.TLabel", background=p.carte, foreground=p.doux, font="AppCorps")
    style.configure("CarteGras.TLabel", background=p.carte, foreground=p.texte, font="AppGras")
    style.configure("CarteErreur.TLabel", background=p.carte, foreground=p.rouge, font="AppCorps")
    style.configure("Bloquant.TLabel", background=p.fond, foreground=p.rouge, font="AppGras")
    style.configure("Alerte.TLabel", background=p.fond, foreground=p.orange, font="AppGras")
    style.configure("Bon.TLabel", background=p.fond, foreground=p.vert, font="AppGras")
    style.configure("Carte.TLabelframe", background=p.carte, bordercolor=p.bordure, relief="solid")
    style.configure("Carte.TLabelframe.Label", background=p.carte, foreground=p.texte, font="AppCarte")
    style.configure("TSeparator", background=p.bordure)
    style.configure("TNotebook", background=p.fond, bordercolor=p.bordure)
    style.configure("TNotebook.Tab", background=p.entete, foreground=p.texte, padding=(12, 6))
    style.map("TNotebook.Tab", background=[("selected", p.carte)])
    style.configure("Horizontal.TProgressbar", background=p.accent, troughcolor=p.entete, bordercolor=p.bordure)
    style.configure("TScrollbar", background=p.entete, troughcolor=p.fond, bordercolor=p.bordure, arrowcolor=p.texte)
    style.configure("TScrollbar", lightcolor=p.entete, darkcolor=p.entete)
    style.map("TScrollbar", background=[("disabled", p.fond), ("active", p.selection)])


def _boutons(style: ttk.Style) -> None:
    p = _courante
    style.configure("TButton", font="AppGras", padding=(10, 6), background=p.entete, foreground=p.texte)
    style.configure("TButton", bordercolor=p.bordure, lightcolor=p.entete, darkcolor=p.entete)
    style.map(
        "TButton",
        background=[("disabled", p.fond), ("active", p.selection)],
        foreground=[("disabled", p.doux)],
    )
    style.configure("Accent.TButton", background=p.accent, foreground=p.sur_accent)
    style.configure("Accent.TButton", bordercolor=p.accent_appui, lightcolor=p.accent, darkcolor=p.accent)
    style.map(
        "Accent.TButton",
        background=[("disabled", p.inactif), ("pressed", p.accent_appui), ("active", p.accent_appui)],
        foreground=[("disabled", p.sur_inactif)],
    )
    style.configure(
        "Rail.TButton", font="AppCorps", padding=(10, 8), anchor="w", background=p.entete, foreground=p.texte
    )
    style.map(
        "Rail.TButton",
        background=[("active", p.selection)],
        foreground=[("disabled", p.doux)],
    )
    style.configure("Petit.TButton", font="AppCorps", padding=(6, 0))  # bouton discret d'une carte (journal)
    style.configure("RailActif.TButton", font="AppGras", padding=(10, 8), anchor="w")
    style.configure("RailActif.TButton", background=p.accent, foreground=p.sur_accent)
    style.map("RailActif.TButton", background=[("active", p.accent_appui)])
    for nom in ("TCheckbutton", "TRadiobutton"):
        style.configure(nom, background=p.carte, foreground=p.texte, font="AppCorps")
        style.configure(nom, indicatorbackground=p.carte, indicatorforeground=p.texte, bordercolor=p.bordure)
        style.map(nom, background=[("active", p.carte)], foreground=[("disabled", p.doux)])


def _tableaux(style: ttk.Style, pourcentage: int) -> None:
    p = _courante
    hauteur = taille_police(HAUTEUR_LIGNE, pourcentage)
    style.configure(
        "Treeview", background=p.carte, fieldbackground=p.carte, foreground=p.texte, rowheight=hauteur, font="AppCorps"
    )
    style.configure("Treeview", bordercolor=p.bordure, lightcolor=p.bordure, darkcolor=p.bordure)
    style.map("Treeview", background=[("selected", p.selection)], foreground=[("selected", p.texte_selection)])
    style.configure("Treeview.Heading", background=p.entete, foreground=p.texte, font="AppGras")
    style.configure("Treeview.Heading", bordercolor=p.bordure, lightcolor=p.entete, darkcolor=p.entete)
    style.map("Treeview.Heading", background=[("active", p.selection)])


def _champs(style: ttk.Style) -> None:
    p = _courante
    for nom in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            nom,
            fieldbackground=p.carte,
            background=p.carte,
            foreground=p.texte,
            bordercolor=p.bordure,
            lightcolor=p.bordure,
            darkcolor=p.bordure,
            insertcolor=p.texte,
        )
        style.map(nom, fieldbackground=[("readonly", p.carte), ("disabled", p.fond)], foreground=[("disabled", p.doux)])
    style.map("TCombobox", selectbackground=[("readonly", p.carte)], selectforeground=[("readonly", p.texte)])


def recolorier(racine: tk.Misc) -> None:
    """Reprend les couleurs de la palette courante dans les composants Tk classiques déjà créés.

    Les composants ttk suivent les styles ; les `Canvas`, `Text`, `Menu` et `Listbox` gardent leurs couleurs
    d'origine tant qu'on ne les reconfigure pas.
    """
    p = _courante
    for enfant in racine.winfo_children():
        with contextlib.suppress(tk.TclError):
            if isinstance(enfant, tk.Canvas):
                enfant.configure(background=p.fond)
            elif isinstance(enfant, tk.Text):
                enfant.configure(
                    background=p.carte,
                    foreground=p.texte,
                    insertbackground=p.texte,
                    selectbackground=p.selection,
                    selectforeground=p.texte_selection,
                    highlightbackground=p.bordure,
                    highlightcolor=p.bordure,
                )
            elif isinstance(enfant, tk.Menu):
                enfant.configure(
                    background=p.carte,
                    foreground=p.texte,
                    activebackground=p.selection,
                    activeforeground=p.texte_selection,
                )
        recolorier(enfant)


# ============================================================
# FIGURES AU THÈME
# ============================================================
def _table_des_couleurs(palette: Palette) -> dict[str, str]:
    """Couleur de la charte claire vers la couleur de même rôle dans `palette` (première rencontrée par valeur)."""
    table: dict[str, str] = {}
    for jeton in fields(Palette):
        claire = getattr(PALETTES["clair"], jeton.name).lower()
        table.setdefault(claire, getattr(palette, jeton.name))
    return table


def _couleur_au_theme(couleur: Any, table: dict[str, str], sombre: str) -> Any:
    """Couleur traduite : jeton de la charte claire vers la palette, encre foncée vers `sombre`, le reste tel quel.

    Une couleur transparente ou illisible est gardée ; la transparence d'une couleur traduite est conservée.
    """
    from matplotlib.colors import to_hex, to_rgba

    try:
        rgba = to_rgba(couleur)
    except (TypeError, ValueError):
        return couleur
    if rgba[3] == 0:
        return couleur
    code = to_hex(rgba, keep_alpha=False).lower()
    if code in table:
        return to_rgba(table[code], alpha=rgba[3])
    return to_rgba(sombre, alpha=rgba[3]) if luminance(code) < 0.18 else couleur


def habiller_figure(figure: Any, palette: Palette | None = None) -> Any:
    """Reprend fond, textes, axes, quadrillage et couleurs de la charte de la figure dans la palette (en place)."""
    from matplotlib.collections import Collection
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.text import Text

    p = palette or _courante
    table = _table_des_couleurs(p)
    for objet in figure.findobj():
        if isinstance(objet, Text | Line2D):
            objet.set_color(_couleur_au_theme(objet.get_color(), table, p.texte))
        elif isinstance(objet, Patch):
            objet.set_facecolor(_couleur_au_theme(objet.get_facecolor(), table, p.carte))
            objet.set_edgecolor(_couleur_au_theme(objet.get_edgecolor(), table, p.doux))
        elif isinstance(objet, Collection):
            objet.set_facecolor([_couleur_au_theme(c, table, p.texte) for c in objet.get_facecolor()])
            objet.set_edgecolor([_couleur_au_theme(c, table, p.doux) for c in objet.get_edgecolor()])
    for axes in figure.axes:
        axes.set_facecolor(p.carte)
        axes.tick_params(colors=p.doux, labelcolor=p.texte)
    figure.set_facecolor(p.carte)
    return figure


def figure_au_theme(figure: Any) -> Any:
    """Figure à afficher dans le thème courant.

    Thème clair : la figure du noyau elle-même. Thème sombre : une copie habillée aux couleurs de la palette ; la
    figure d'origine, qui sert à l'export et à l'enregistrement d'une image, n'est jamais modifiée. Une figure qui
    ne se copie pas est montrée telle quelle.
    """
    if _courante == PALETTES["clair"]:
        return figure
    try:
        copie = copy.deepcopy(figure)
    except (TypeError, ValueError, AttributeError, RecursionError):
        return figure
    return habiller_figure(copie, _courante)
