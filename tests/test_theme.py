"""Thème : contrastes des deux palettes (WCAG 2), polices de repli, taille réglable. Aucun écran requis."""

from __future__ import annotations

import pytest

from codap_c_97_jupe_fond.ui import theme

# Paires de texte : 4,5 au moins. Les éléments d'interface (focus, liens) : 3 au moins. Un bouton plein est reconnu
# à son libellé (texte sur accent) ; le bouton désactivé est exempté, comme le veut la règle des composants inactifs.
TEXTES = (
    ("texte", "fond"),
    ("texte", "carte"),
    ("doux", "carte"),
    ("doux", "fond"),
    ("sur_accent", "accent"),
    ("sur_accent", "accent_appui"),
    ("lien", "carte"),
    ("rouge", "carte"),
    ("orange", "carte"),
    ("vert", "carte"),
    ("rouge", "fond"),
    ("orange", "fond"),
    ("vert", "fond"),
    ("texte_selection", "selection"),
    ("texte", "entete"),
)


@pytest.mark.parametrize("nom", sorted(theme.PALETTES))
def test_chaque_texte_a_un_contraste_d_au_moins_4_5(nom: str) -> None:
    palette = theme.PALETTES[nom]
    faibles = {
        (a, b): round(theme.contraste(getattr(palette, a), getattr(palette, b)), 2)
        for a, b in TEXTES
        if theme.contraste(getattr(palette, a), getattr(palette, b)) < 4.5
    }
    assert faibles == {}


@pytest.mark.parametrize("nom", sorted(theme.PALETTES))
def test_les_elements_d_interface_ont_un_contraste_d_au_moins_3(nom: str) -> None:
    palette = theme.PALETTES[nom]
    assert theme.contraste(palette.lien, palette.carte) >= 3.0  # anneau de focus et liens
    assert theme.contraste(palette.texte, palette.bordure) >= 3.0  # le texte reste lisible sur un filet
    # le bouton principal et l'étape active se distinguent de la carte et du fond (contrôle V23)
    assert theme.contraste(palette.accent, palette.carte) >= 3.0
    assert theme.contraste(palette.accent, palette.fond) >= 3.0


def test_les_valeurs_mesurees_de_la_palette_sombre() -> None:
    sombre = theme.PALETTES["sombre"]
    assert theme.contraste(sombre.texte, sombre.carte) == pytest.approx(12.75, abs=0.02)
    assert theme.contraste(sombre.sur_accent, sombre.accent) == pytest.approx(4.89, abs=0.02)
    assert theme.contraste(sombre.accent, sombre.carte) == pytest.approx(3.13, abs=0.02)
    assert theme.contraste(sombre.sur_accent, sombre.accent_appui) == pytest.approx(7.14, abs=0.02)
    assert theme.contraste(sombre.doux, sombre.carte) == pytest.approx(6.85, abs=0.02)
    assert theme.contraste(sombre.lien, sombre.carte) >= 7.0


def test_les_valeurs_mesurees_de_la_palette_claire() -> None:
    claire = theme.PALETTES["clair"]
    assert theme.contraste(claire.texte, claire.carte) == pytest.approx(16.19, abs=0.02)
    assert theme.contraste(claire.sur_accent, claire.accent) == pytest.approx(7.03, abs=0.02)


def test_le_contraste_est_symetrique_et_borne() -> None:
    assert theme.contraste("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert theme.contraste("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert theme.contraste("#336699", "#336699") == pytest.approx(1.0)


def test_la_premiere_police_disponible_est_choisie_sans_tenir_compte_de_la_casse() -> None:
    assert theme.choisir_famille(["Segoe UI", "DejaVu Sans"], ["Arial", "dejavu sans"]) == "dejavu sans"
    assert theme.choisir_famille(["Segoe UI"], ["Arial"]) == "TkDefaultFont"
    assert theme.choisir_famille(["Segoe UI"], [], repli="TkFixedFont") == "TkFixedFont"


def _figure() -> object:
    from matplotlib.figure import Figure

    figure = Figure(figsize=(3, 2))
    axes = figure.subplots()
    axes.plot([0, 1], [0, 1], color=theme.PALETTES["clair"].accent)
    axes.bar([0.5], [0.4], color="#ABCDEF")
    axes.set_title("titre")
    axes.grid(True, color=theme.PALETTES["clair"].bordure)
    return figure


def test_une_figure_en_theme_sombre_est_une_copie_habillee_et_l_original_reste_clair() -> None:
    from matplotlib.colors import to_hex

    figure = _figure()
    sombre = theme.PALETTES["sombre"]
    try:
        theme._courante = sombre
        copie = theme.figure_au_theme(figure)
    finally:
        theme._courante = theme.PALETTES["clair"]
    assert copie is not figure
    assert to_hex(copie.get_facecolor()).upper() == sombre.carte
    assert to_hex(copie.axes[0].lines[0].get_color()).upper() == sombre.accent, "le jeton de la charte est traduit"
    assert to_hex(copie.axes[0].title.get_color()).upper() == sombre.texte, "l'encre foncée devient claire"
    assert to_hex(copie.axes[0].patches[0].get_facecolor()).upper() == "#ABCDEF", "une couleur de donnée est gardée"
    # l'original, qui sert à l'export, n'a pas bougé
    assert to_hex(figure.get_facecolor()).upper() == "#FFFFFF"
    assert to_hex(figure.axes[0].lines[0].get_color()).upper() == theme.PALETTES["clair"].accent


def test_en_theme_clair_la_figure_du_noyau_est_montree_telle_quelle() -> None:
    figure = _figure()
    theme._courante = theme.PALETTES["clair"]
    assert theme.figure_au_theme(figure) is figure


def test_la_taille_de_police_suit_le_pourcentage_avec_un_plancher() -> None:
    assert [theme.taille_police(10, p) for p in (80, 100, 130, 160)] == [8, 10, 13, 16]
    assert theme.taille_police(8, 80) == 7
