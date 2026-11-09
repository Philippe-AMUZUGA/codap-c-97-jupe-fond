"""Composants graphiques partagés par les écrans (aucune règle de calcul ici)."""

from __future__ import annotations

import contextlib
import sys
import tkinter as tk
import weakref
from collections.abc import Callable, Iterable, Sequence
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

from ..textes import t
from . import theme

__all__ = [
    "Banniere",
    "Colonne",
    "GrilleSaisie",
    "Infobulle",
    "ScrollableFrame",
    "Tableau",
    "ZoneFigure",
    "ZoneJournal",
    "carte",
    "pas_de_molette",
]

Colonne = tuple[str, str, int, str]  # (clé, titre, largeur en pixels, ancre)

_CLASSES_AVEC_MOLETTE_PROPRE = frozenset({"Treeview", "Text", "Listbox", "TCombobox"})


def carte(parent: tk.Misc, titre: str, **options: Any) -> ttk.LabelFrame:
    """Carte à filet fin, comme les cadres de l'application de référence."""
    return ttk.LabelFrame(parent, text=titre, style="Carte.TLabelframe", padding=options.pop("padding", 12), **options)


# ============================================================
# ZONE DÉFILANTE (Windows, macOS, Linux)
# ============================================================
def pas_de_molette(delta: int, plateforme: str | None = None) -> int:
    """Unités de défilement vertical (positif : vers le bas) pour un événement `<MouseWheel>`.

    Windows donne des multiples de 120 par cran (un cran, une unité) ; macOS donne de petits entiers, déjà
    en unités ; un pavé tactile à haute résolution donne moins de 120 : l'unité est alors le minimum.
    """
    plateforme = plateforme or sys.platform
    if delta == 0:
        return 0
    if plateforme == "darwin":
        return -delta
    return -int(delta / 120) or (-1 if delta > 0 else 1)


_ZONES_PAR_RACINE: weakref.WeakKeyDictionary[tk.Misc, bool] = weakref.WeakKeyDictionary()


def _poser_molette(racine: tk.Misc) -> None:
    """Une seule liaison globale par fenêtre : la molette défile la zone qui est sous le pointeur."""
    if racine in _ZONES_PAR_RACINE:
        return
    _ZONES_PAR_RACINE[racine] = True
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        racine.bind_all(sequence, lambda e, r=racine: _distribuer(r, e), add="+")


def _distribuer(racine: tk.Misc, evenement: tk.Event) -> None:
    try:
        sous = racine.winfo_containing(evenement.x_root, evenement.y_root)
    except (KeyError, tk.TclError):
        return
    if sous is None or sous.winfo_class() in _CLASSES_AVEC_MOLETTE_PROPRE:
        return
    cible: tk.Misc | None = sous
    while cible is not None:
        if isinstance(cible, ScrollableFrame):
            cible.defiler(evenement)
            return
        cible = cible.master


class ScrollableFrame(ttk.Frame):
    """Zone à défilement vertical : le contenu se place dans `interieur`. La molette marche sur les trois systèmes."""

    def __init__(self, parent: tk.Misc, **options: Any) -> None:
        super().__init__(parent, **options)
        self.toile = tk.Canvas(self, background=theme.couleurs().fond, highlightthickness=0)
        self.barre = ttk.Scrollbar(self, orient="vertical", command=self.toile.yview)
        self.toile.configure(yscrollcommand=self.barre.set)
        self.interieur = ttk.Frame(self.toile)
        self._fenetre = self.toile.create_window((0, 0), window=self.interieur, anchor="nw")
        self.toile.grid(row=0, column=0, sticky="nsew")
        self.barre.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.interieur.bind("<Configure>", lambda _e: self.toile.configure(scrollregion=self.toile.bbox("all")))
        self.toile.bind("<Configure>", lambda e: self.toile.itemconfigure(self._fenetre, width=e.width))
        _poser_molette(self._root())

    def montrer(self, composant: tk.Misc) -> None:
        """Amène le haut d'un composant de la zone en haut de la fenêtre visible (rien si tout est visible)."""
        self.update_idletasks()
        total = self.interieur.winfo_height()
        if total <= self.toile.winfo_height():
            return
        decalage = composant.winfo_rooty() - self.interieur.winfo_rooty()
        self.toile.yview_moveto(max(0.0, min(1.0, (decalage - 8) / total)))

    def defiler(self, evenement: tk.Event) -> None:
        """Fait défiler la zone d'un cran de molette (rien si tout le contenu est visible)."""
        numero = getattr(evenement, "num", 0)
        pas = 1 if numero == 5 else -1 if numero == 4 else pas_de_molette(getattr(evenement, "delta", 0))
        with contextlib.suppress(tk.TclError):
            debut, fin = self.toile.yview()
            if debut > 0.0 or fin < 1.0:
                self.toile.yview_scroll(pas, "units")


# ============================================================
# TABLEAU
# ============================================================
def _police_des_entetes() -> tkfont.Font | None:
    """Police des en-têtes de tableau, pour mesurer les titres ; None si elle ne se lit pas."""
    try:
        nom = ttk.Style().lookup("Treeview.Heading", "font") or "TkHeadingFont"
        return tkfont.nametofont(nom) if nom in tkfont.names() else tkfont.Font(font=nom)
    except tk.TclError:
        return None


def _barre_si_utile(barre: ttk.Scrollbar, grille: dict[str, Any]) -> Callable[[str, str], None]:
    """Commande de défilement d'un composant : la barre n'apparaît que si tout le contenu n'est pas visible."""

    def regler(debut: str, fin: str) -> None:
        if float(debut) <= 0.0 and float(fin) >= 1.0:
            barre.grid_remove()
        else:
            barre.grid(**grille)
        barre.set(debut, fin)

    return regler


class Tableau(ttk.Frame):
    """Tableau (Treeview) à barres de défilement, rempli par des lignes de textes ; Ctrl+C copie la sélection."""

    def __init__(
        self, parent: tk.Misc, colonnes: Sequence[Colonne], hauteur: int = 8, selection: str = "extended"
    ) -> None:
        super().__init__(parent)
        self.cles = [c[0] for c in colonnes]
        self.arbre = ttk.Treeview(self, columns=self.cles, show="headings", selectmode=selection, height=hauteur)
        police = _police_des_entetes()
        for rang, (cle, titre, largeur, ancre) in enumerate(colonnes):
            self.arbre.heading(cle, text=titre)
            if police is not None:
                largeur = max(largeur, police.measure(titre) + 32)  # un en-tête n'est jamais tronqué
            # seule la dernière colonne s'étire : les autres gardent leur largeur, le défilement fait le reste
            self.arbre.column(cle, width=largeur, anchor=ancre, stretch=rang == len(colonnes) - 1, minwidth=40)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.arbre.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.arbre.xview)
        self.arbre.configure(
            yscrollcommand=_barre_si_utile(vertical, {"row": 0, "column": 1, "sticky": "ns"}),
            xscrollcommand=_barre_si_utile(horizontal, {"row": 1, "column": 0, "sticky": "ew"}),
        )
        self.arbre.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.arbre.bind("<Control-c>", lambda _e: self.copier())
        self.arbre.bind("<Command-c>", lambda _e: self.copier())

    def vider(self) -> None:
        self.arbre.delete(*self.arbre.get_children())

    def ajouter(self, valeurs: Iterable[Any], iid: str | None = None, etiquettes: Sequence[str] = ()) -> str:
        """Ajoute une ligne ; rend son identifiant."""
        textes = tuple("" if v is None else str(v) for v in valeurs)
        return self.arbre.insert("", "end", iid=iid, values=textes, tags=tuple(etiquettes))

    def remplir(
        self, lignes: Iterable[Iterable[Any]], etiquettes: Callable[[int], Sequence[str]] | None = None
    ) -> None:
        self.vider()
        for k, valeurs in enumerate(lignes):
            self.ajouter(valeurs, iid=str(k), etiquettes=etiquettes(k) if etiquettes else ())

    def selection(self) -> tuple[str, ...]:
        return tuple(self.arbre.selection())

    def lignes(self) -> list[tuple[str, ...]]:
        """Contenu affiché, ligne par ligne."""
        return [tuple(self.arbre.item(i, "values")) for i in self.arbre.get_children()]

    def copier(self) -> str:
        """Copie les lignes choisies (toutes s'il n'y en a pas) dans le presse-papiers, séparées par des tabulations."""
        choix = self.arbre.selection() or self.arbre.get_children()
        texte = "\n".join("\t".join(str(v) for v in self.arbre.item(i, "values")) for i in choix)
        self.clipboard_clear()
        self.clipboard_append(texte)
        return texte

    def colorier(self, etiquette: str, couleur: str) -> None:
        self.arbre.tag_configure(etiquette, foreground=couleur)

    def lier_selection(self, rappel: Callable[[tuple[str, ...]], None]) -> None:
        self.arbre.bind("<<TreeviewSelect>>", lambda _e: rappel(self.selection()))


# ============================================================
# GRILLE DE SAISIE (entrée de type tableau)
# ============================================================
class GrilleSaisie(ttk.Frame):
    """Saisie d'un tableau : en-têtes (libellé et unité de chaque colonne), une rangée de saisies par ligne, et deux
    boutons pour ajouter ou retirer la dernière ligne, dans les bornes du nombre de lignes.

    `colonnes` sont des champs du schéma (`core.schema.Champ`) ; la grille ne valide rien : `brut()` rend les textes
    saisis, ligne par ligne, et la validation commune les contrôle.
    """

    LARGEUR = 12

    def __init__(
        self,
        parent: tk.Misc,
        colonnes: Sequence[Any],
        langue: str,
        *,
        lignes_min: int = 0,
        lignes_max: int = 1000,
        au_changement: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Carte.TFrame")
        self.colonnes = tuple(colonnes)
        self.langue = langue
        self.bornes = (lignes_min, lignes_max)
        self._au_changement = au_changement
        self.rangees: list[list[tuple[tk.Variable, tk.Widget]]] = []
        self._occupe = False
        for k, colonne in enumerate(self.colonnes):
            titre = colonne.libelle_dans(langue) + (f" ({colonne.unite})" if colonne.unite else "")
            ttk.Label(self, text=titre, style="CarteGras.TLabel").grid(row=0, column=k, sticky="w", padx=(0, 8))
        self.boutons = ttk.Frame(self, style="Carte.TFrame")
        self.ajout = ttk.Button(self.boutons, text=t("tableau.ajouter"), command=self.ajouter_ligne)
        self.ajout.grid(row=0, column=0, padx=(0, 8))
        self.retrait = ttk.Button(self.boutons, text=t("tableau.retirer"), command=self.retirer_ligne)
        self.retrait.grid(row=0, column=1)
        self._placer_boutons()

    def _cellule(self, colonne: Any) -> tuple[tk.Variable, tk.Widget]:
        if colonne.type == "booleen":
            variable: tk.Variable = tk.BooleanVar(master=self)
            return variable, ttk.Checkbutton(self, variable=variable)
        variable = tk.StringVar(master=self)
        if colonne.type == "choix":
            valeurs = [colonne.etiquette_dans(v, self.langue) for v in colonne.choix]
            liste = ttk.Combobox(self, textvariable=variable, values=valeurs, state="readonly", width=self.LARGEUR)
            return variable, liste
        return variable, ttk.Entry(self, textvariable=variable, width=self.LARGEUR)

    def _placer_boutons(self) -> None:
        largeur = max(1, len(self.colonnes))
        self.boutons.grid(row=len(self.rangees) + 1, column=0, columnspan=largeur, sticky="w", pady=(6, 0))
        nombre = len(self.rangees)
        self.ajout.configure(state="disabled" if self._occupe or nombre >= self.bornes[1] else "normal")
        self.retrait.configure(state="disabled" if self._occupe or nombre <= self.bornes[0] else "normal")

    def ajouter_ligne(self, valeurs: Sequence[Any] | None = None) -> None:
        """Ajoute une ligne en bas (valeurs dans l'ordre des colonnes, sinon les défauts des colonnes)."""
        if len(self.rangees) >= self.bornes[1]:
            return
        rang = len(self.rangees) + 1
        rangee = []
        for k, colonne in enumerate(self.colonnes):
            variable, saisie = self._cellule(colonne)
            saisie.grid(row=rang, column=k, sticky="w", padx=(0, 8), pady=(2, 0))
            valeur = valeurs[k] if valeurs is not None else colonne.defaut
            self._poser(colonne, variable, valeur)
            variable.trace_add("write", lambda *_: self._a_change())
            rangee.append((variable, saisie))
        self.rangees.append(rangee)
        self._placer_boutons()
        self._a_change()

    def retirer_ligne(self) -> None:
        """Retire la dernière ligne (jamais sous le nombre minimal de lignes)."""
        if len(self.rangees) <= self.bornes[0]:
            return
        for _, saisie in self.rangees.pop():
            saisie.destroy()
        self._placer_boutons()
        self._a_change()

    def _poser(self, colonne: Any, variable: tk.Variable, valeur: Any) -> None:
        if colonne.type == "booleen":
            variable.set(bool(valeur))
        elif colonne.type == "choix":
            variable.set("" if valeur is None else colonne.etiquette_dans(str(valeur), self.langue))
        else:
            variable.set("" if valeur is None else str(valeur))

    def _a_change(self) -> None:
        if self._au_changement is not None:
            self._au_changement()

    def definir(self, lignes: Iterable[Any] | None) -> None:
        """Remplace toutes les lignes : chacune est une liste dans l'ordre des colonnes ou un objet nom vers valeur."""
        while self.rangees:
            for _, saisie in self.rangees.pop():
                saisie.destroy()
        for ligne in lignes or ():
            if isinstance(ligne, dict):
                ligne = [ligne.get(c.nom, c.defaut) for c in self.colonnes]
            self.ajouter_ligne(list(ligne))
        self._placer_boutons()

    def brut(self) -> list[list[Any]]:
        """Valeurs saisies, ligne par ligne, avant validation (valeur réelle d'un choix, pas son étiquette)."""
        lignes = []
        for rangee in self.rangees:
            ligne = []
            for colonne, (variable, _) in zip(self.colonnes, rangee, strict=True):
                saisi = variable.get()
                if colonne.type == "choix":
                    saisi = {colonne.etiquette_dans(v, self.langue): v for v in colonne.choix}.get(saisi, saisi)
                ligne.append(saisi)
            lignes.append(ligne)
        return lignes

    def basculer(self, occupe: bool) -> None:
        """Grise les saisies et les boutons pendant un calcul."""
        self._occupe = occupe
        for rangee in self.rangees:
            for _, saisie in rangee:
                etat = "readonly" if isinstance(saisie, ttk.Combobox) else "normal"
                saisie.configure(state="disabled" if occupe else etat)
        self._placer_boutons()


# ============================================================
# FIGURE, JOURNAL, BANDEAU, AIDE
# ============================================================
class ZoneFigure(ttk.Frame):
    """Zone d'une figure matplotlib (construite par le noyau, sans moteur graphique).

    La figure est montrée aux couleurs du thème courant (`theme.figure_au_theme` : une copie en thème sombre) ;
    `figure` reste l'original du noyau, celui qu'on enregistre. Avec `au_enregistrement`, un bouton sous la figure
    propose de l'enregistrer en image (PNG ou SVG) : la fenêtre ouvre le dialogue et écrit le fichier.
    """

    def __init__(
        self,
        parent: tk.Misc,
        largeur: int = 640,
        hauteur: int = 340,
        au_enregistrement: Callable[[Any], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Carte.TFrame")
        self._taille = (largeur, hauteur)
        self._toile: Any = None
        self.figure: Any = None
        self.affichee: Any = None
        self.grid_columnconfigure(0, weight=1)
        self.bouton: ttk.Button | None = None
        if au_enregistrement is not None:
            self.bouton = ttk.Button(
                self,
                text=t("image.enregistrer"),
                command=lambda: au_enregistrement(self.figure) if self.figure is not None else None,
            )
            self.bouton.grid(row=1, column=0, sticky="e", pady=(6, 0))

    def afficher(self, figure: Any, *, naturelle: bool = False) -> None:
        """Remplace la figure affichée ; l'ancienne est libérée.

        `naturelle` : la zone prend la hauteur de la figure (en pouces, quelle que soit l'échelle de l'écran) et sa
        largeur suit la carte ; sinon, la taille fixe donnée à la création.
        """
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.effacer()
        self.figure = figure
        self.affichee = theme.figure_au_theme(figure)
        self._toile = FigureCanvasTkAgg(self.affichee, master=self)
        graphique = self._toile.get_tk_widget()
        if not naturelle:
            graphique.configure(width=self._taille[0], height=self._taille[1])
        graphique.grid(row=0, column=0, sticky="ew" if naturelle else "nsew")
        self._toile.draw()

    def enregistrer(self, chemin: str) -> Any:
        """Écrit la figure d'origine en PNG ou en SVG (selon l'extension) ; rend le chemin écrit."""
        from ..core.export import enregistrer_figure

        if self.figure is None:
            raise ValueError("aucune figure à enregistrer")
        return enregistrer_figure(self.figure, chemin)

    def effacer(self) -> None:
        if self._toile is not None:
            self._toile.get_tk_widget().destroy()
        self._toile = None
        self.figure = None
        self.affichee = None


class ZoneJournal(ttk.Frame):
    """Journal visible : lignes ajoutées en bas, couleur selon le niveau, 1000 lignes au plus.

    Replié, il ne montre que sa dernière ligne : la zone centrale de la fenêtre garde sa hauteur sur un petit écran.
    """

    LIGNES_MAX = 1000
    LIGNES_REPLIE = 1

    def __init__(self, parent: tk.Misc, hauteur: int = 6) -> None:
        super().__init__(parent)
        self.hauteur = hauteur
        self.replie = False
        p = theme.couleurs()
        self.texte = tk.Text(
            self,
            height=hauteur,
            wrap="word",
            font="AppMono",
            background=p.carte,
            foreground=p.texte,
            insertbackground=p.texte,
            selectbackground=p.selection,
            selectforeground=p.texte_selection,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=p.bordure,
            highlightcolor=p.bordure,
            state="disabled",
        )
        self.barre = ttk.Scrollbar(self, orient="vertical", command=self.texte.yview)
        self.texte.configure(yscrollcommand=self.barre.set)
        self.texte.grid(row=0, column=0, sticky="nsew")
        self.barre.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.colorier()

    def colorier(self) -> None:
        """Couleurs des niveaux selon la palette courante."""
        p = theme.couleurs()
        self.texte.tag_configure("ERROR", foreground=p.rouge)
        self.texte.tag_configure("CRITICAL", foreground=p.rouge)
        self.texte.tag_configure("WARNING", foreground=p.orange)

    def ajouter(self, lignes: Iterable[str]) -> None:
        """Ajoute des lignes (déjà formatées) et descend en bas."""
        lignes = list(lignes)
        if not lignes:
            return
        self.texte.configure(state="normal")
        for ligne in lignes:
            niveau = next((n for n in ("CRITICAL", "ERROR", "WARNING") if f" {n} " in ligne), "")
            self.texte.insert("end", ligne + "\n", (niveau,) if niveau else ())
        total = int(self.texte.index("end-1c").split(".")[0])
        if total > self.LIGNES_MAX:
            self.texte.delete("1.0", f"{total - self.LIGNES_MAX + 1}.0")
        self.texte.see("end")
        self.texte.configure(state="disabled")

    def contenu(self) -> str:
        return self.texte.get("1.0", "end").strip()

    def replier(self, replie: bool) -> None:
        """Replié : une ligne, la dernière ; déplié : la hauteur donnée à la création."""
        self.replie = bool(replie)
        self.texte.configure(height=self.LIGNES_REPLIE if self.replie else self.hauteur)
        if self.replie:  # la barre de défilement a une hauteur minimale : repliée, elle cède la place
            self.barre.grid_remove()
        else:
            self.barre.grid()
        self.texte.see("end")


class Banniere(ttk.Frame):
    """Bandeau de message en tête d'écran : erreur, avertissement ou information, avec fermeture."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.message = ttk.Label(self, text="", style="Bloquant.TLabel", wraplength=900, justify="left")
        self.message.grid(row=0, column=0, sticky="ew")
        self.fermer = ttk.Button(self, text=t("commun.fermer"), command=self.masquer)
        self.fermer.grid(row=0, column=1, padx=(10, 0))
        self.grid_columnconfigure(0, weight=1)
        self.bind("<Configure>", lambda e: self.message.configure(wraplength=max(200, e.width - 120)))
        self.niveau = ""  # bloquant, alerte, bon ; vide quand le bandeau est fermé
        self.grid_remove()

    def afficher(self, texte: str, niveau: str = "bloquant") -> None:
        style = {"bloquant": "Bloquant.TLabel", "alerte": "Alerte.TLabel", "bon": "Bon.TLabel"}.get(niveau, "TLabel")
        self.message.configure(text=texte, style=style)
        self.niveau = niveau
        self.grid()

    def masquer(self) -> None:
        self.message.configure(text="")
        self.niveau = ""
        self.grid_remove()

    @property
    def texte(self) -> str:
        return str(self.message.cget("text"))

    @property
    def visible(self) -> bool:
        return bool(self.winfo_manager())


class Infobulle:
    """Texte d'aide d'un composant, affiché après un court survol (le texte est relu à chaque affichage)."""

    DELAI_MS = 500

    def __init__(self, composant: tk.Misc, texte: Callable[[], str]) -> None:
        self.composant, self.texte = composant, texte
        self._bulle: tk.Toplevel | None = None
        self._attente: str | None = None
        composant.bind("<Enter>", self._programmer, add="+")
        for evenement in ("<Leave>", "<ButtonPress>", "<FocusOut>"):
            composant.bind(evenement, self._cacher, add="+")

    def _programmer(self, _evenement: tk.Event) -> None:
        self._cacher()
        self._attente = self.composant.after(self.DELAI_MS, self._montrer)

    def _montrer(self) -> None:
        self._attente = None
        texte = self.texte()
        if not texte or self._bulle is not None or not self.composant.winfo_exists():
            return
        bulle = tk.Toplevel(self.composant)
        bulle.wm_overrideredirect(True)
        x = self.composant.winfo_rootx() + 16
        y = self.composant.winfo_rooty() + self.composant.winfo_height() + 4
        bulle.wm_geometry(f"+{x}+{y}")
        etiquette = ttk.Label(bulle, text=texte, style="Carte.TLabel", relief="solid", borderwidth=1, padding=6)
        etiquette.configure(wraplength=360, justify="left")
        etiquette.pack()
        self._bulle = bulle

    def _cacher(self, _evenement: tk.Event | None = None) -> None:
        if self._attente is not None:
            with contextlib.suppress(tk.TclError):
                self.composant.after_cancel(self._attente)
            self._attente = None
        if self._bulle is not None:
            with contextlib.suppress(tk.TclError):
                self._bulle.destroy()
            self._bulle = None
