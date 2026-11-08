"""
Interface : la vraie fenêtre, pilotée par les appels de ses boutons ; sautée si le poste n'a pas d'écran.

Les boîtes de dialogue sont remplacées par `DialoguesAutomatiques` (aucun clic) et les pages web par un
enregistreur : rien ne s'ouvre hors de la fenêtre. Sous Linux sans écran, lancer ces tests sous `xvfb-run`.
"""

from __future__ import annotations

import gc
import logging
import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from types import SimpleNamespace

import pytest

from codap_c_97_jupe_fond import URL_RELEASES, __version__, textes
from codap_c_97_jupe_fond.core import calculs, export
from codap_c_97_jupe_fond.core.erreurs import ErreurCalcul, ErreurSaisie
from codap_c_97_jupe_fond.core.schema import Champ, charger_schema, valider
from codap_c_97_jupe_fond.essai import attendre_calcul
from codap_c_97_jupe_fond.systeme import journal, preferences
from codap_c_97_jupe_fond.textes import t
from codap_c_97_jupe_fond.ui import theme
from codap_c_97_jupe_fond.ui.app import Application
from codap_c_97_jupe_fond.ui.dialogues import DialoguesAutomatiques
from codap_c_97_jupe_fond.ui.panneaux import PanneauResultats
from codap_c_97_jupe_fond.ui.widgets import ScrollableFrame


@pytest.fixture
def dialogues(tmp_path: Path) -> DialoguesAutomatiques:
    dossier = tmp_path / "export"
    dossier.mkdir()
    return DialoguesAutomatiques(dossier=str(dossier))


@pytest.fixture
def app(dialogues: DialoguesAutomatiques) -> Iterator[Application]:
    fenetre = None
    for _ in range(3):  # Windows refuse parfois un instant la lecture des fichiers de Tk : on réessaie
        try:
            fenetre = Application(dialogues=dialogues)
            break
        except tk.TclError as erreur:
            if "display" in str(erreur).lower():
                pytest.skip(f"pas d'écran : {erreur}")
            time.sleep(0.5)
    if fenetre is None:
        pytest.fail("Tk ne s'ouvre pas")
    fenetre.pages: list[str] = []  # type: ignore[misc]
    fenetre.ouvrir_url = lambda url: fenetre.pages.append(url) or True  # type: ignore[method-assign]
    yield fenetre
    if not fenetre._ferme:
        fenetre.quitter()
    gc.collect()


def panneaux(app: Application) -> list:
    """Tous les panneaux de la fenêtre, quel que soit le style."""
    if app.style == "un":
        return list(app.corps.panneaux)
    return [p for ecran in app.corps.ecrans for p in ecran.panneaux]


def panneau_resultats(app: Application) -> PanneauResultats:
    return next(p for p in panneaux(app) if isinstance(p, PanneauResultats))


def calculer(app: Application) -> None:
    app.calculer()
    attendre_calcul(app, 30)


def champ_numerique(app: Application) -> Champ:
    """Une entrée numérique du schéma (réelle de préférence) : les tests de saisie portent sur elle."""
    champ = next((c for c in app.schema if c.type == "reel"), None) or next(
        (c for c in app.schema if c.type == "entier"), None
    )
    if champ is None:
        pytest.skip("aucune entrée numérique dans ce schéma")
    return champ


def deux_valeurs_valides(champ: Champ) -> tuple[float, float]:
    """Deux valeurs distinctes acceptées par le champ (dans ses bornes, entières pour un entier)."""
    bas, haut = champ.minimum, champ.maximum
    if bas is not None and haut is not None:
        a, b = bas + (haut - bas) * 0.25, bas + (haut - bas) * 0.5
    elif bas is not None:
        a, b = bas + 2.5, bas + 7.5
    elif haut is not None:
        a, b = haut - 2.5, haut - 7.5
    else:
        a, b = 2500.5, 1.0
    if champ.type == "entier":
        return int(a), int(b) if int(b) != int(a) else int(a) + 1
    return round(a, 2), round(b, 2)


# ====================================================================
# Ouverture, calcul
# ====================================================================
def test_la_fenetre_s_ouvre_dans_le_style_declare(app: Application) -> None:
    assert app.title() == t("app.titre")
    assert app.style == app.declaration["application"]["style"]
    attendu = 0 if app.style == "un" else len(app.declaration["ecran"])
    assert app.corps.nombre_ecrans == attendu
    assert app.statut.get() == t("pied.pret") and not app.occupe and not app.banniere.visible


def test_le_formulaire_reprend_les_defauts_du_schema(app: Application) -> None:
    assert app.corps.formulaire.valider() == valider(tuple(c for c in charger_schema() if c.formulaire), {})
    assert set(app.corps.formulaire.widgets) == {c.nom for c in app.schema if c.formulaire}


def test_le_calcul_passe_par_un_fil_et_remplit_les_resultats(app: Application) -> None:
    calculer(app)
    assert app.resultat is not None and app.entrees is not None
    assert app.banniere.texte == t("calcul.fait") and not app.occupe
    panneau = panneau_resultats(app)
    assert len(panneau.mesures.lignes()) == len(app.resultat.mesures)
    assert len(panneau.tableaux) == len(app.resultat.tableaux)
    assert len(panneau.figures) == len(app.resultat.figures)
    assert all(zone.figure is not None for zone in panneau.figures)
    assert app.progression.get() == 0.0


def test_une_saisie_invalide_est_marquee_sous_le_champ_et_rien_n_est_calcule(app: Application) -> None:
    champ = champ_numerique(app)
    autre = next((c for c in app.schema if c.type in ("reel", "entier") and c.nom != champ.nom), None)
    fautifs = [champ] if autre is None else [champ, autre]
    app.corps.formulaire.definir({c.nom: "abc" for c in fautifs})
    app.calculer()
    assert app.resultat is None and not app.occupe
    assert app.corps.formulaire.message(champ.nom).startswith(champ.libelle_dans(textes.langue()))
    assert app.banniere.visible
    if autre is not None:
        assert app.banniere.texte.startswith(t("saisie.plusieurs", n=2, premier="")[:14])
    app.corps.formulaire.definir({c.nom: c.defaut for c in fautifs})
    assert app.corps.formulaire.message(champ.nom) == champ.aide_dans(textes.langue()), "le message disparaît"


def test_un_calcul_refuse_par_le_noyau_s_affiche_dans_le_bandeau(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_arguments: object, **_options: object) -> None:
        raise ErreurCalcul("erreur.refus", motif="valeurs hors domaine")

    monkeypatch.setattr(calculs, "calculer", refuse)
    calculer(app)
    assert app.resultat is None and app.banniere.visible
    assert "valeurs hors domaine" in app.banniere.texte


def test_les_boutons_sont_grises_pendant_le_calcul(app: Application) -> None:
    app.calculer()
    assert app.occupe and str(app.bouton_annuler.cget("state")) == "normal"
    assert all(str(b.cget("state")) == "disabled" for p in panneaux(app) for b in p._boutons)
    attendre_calcul(app, 30)
    assert all(str(b.cget("state")) == "normal" for p in panneaux(app) for b in p._boutons)
    assert str(app.bouton_annuler.cget("state")) == "disabled"


# ====================================================================
# Fichiers d'entrées
# ====================================================================
def test_enregistrer_puis_ouvrir_des_entrees_et_les_recents(
    app: Application, dialogues: DialoguesAutomatiques, tmp_path: Path
) -> None:
    champ = champ_numerique(app)
    a, b = deux_valeurs_valides(champ)
    fichier = tmp_path / "mes_entrees.json"
    dialogues.fichier = str(fichier)
    app.corps.formulaire.definir({champ.nom: a})
    app.enregistrer()
    assert fichier.is_file() and app.prefs.recents == [str(fichier.resolve())]
    app.corps.formulaire.definir({champ.nom: b})
    app.ouvrir()
    assert app.corps.formulaire.valider()[champ.nom] == a
    assert app.banniere.texte == t("fichier.ouvert", nom=fichier.name)


def test_un_fichier_invalide_est_refuse_en_entier(
    app: Application, dialogues: DialoguesAutomatiques, tmp_path: Path
) -> None:
    champ = champ_numerique(app)
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text(f'{{"{champ.nom}": "abc", "inconnue": 1}}', encoding="utf-8")
    dialogues.fichier = str(mauvais)
    avant = app.corps.formulaire.brut()
    app.ouvrir()
    assert app.corps.formulaire.brut() == avant, "rien n'est chargé"
    assert app.banniere.visible and "mauvais.json" in app.banniere.texte
    assert app.prefs.recents == []


def test_l_exemple_se_charge_et_les_defauts_se_remettent(app: Application, entrees_exemple: dict) -> None:
    champ = champ_numerique(app)
    app.charger_exemple()  # formulaire et réglages des écrans (entrées structurées) réunis par saisie_complete
    assert app.saisie_complete() == valider(charger_schema(), entrees_exemple)
    app.corps.formulaire.definir({champ.nom: deux_valeurs_valides(champ)[0]})
    app.valeurs_par_defaut()
    assert app.saisie_complete() == valider(charger_schema(), {})


# ====================================================================
# Export
# ====================================================================
def test_export_sans_resultat_dit_de_calculer_d_abord(app: Application) -> None:
    app.exporter()
    assert app.banniere.texte == t("erreur.pas_de_resultat") and app.derniers_fichiers == []


def test_export_par_l_interface_et_confirmation_avant_d_ecraser(
    app: Application, dialogues: DialoguesAutomatiques
) -> None:
    calculer(app)
    dossier = Path(dialogues.dossier)
    attendus = sorted(export.fichiers_a_ecrire(app.resultat, "essai", ("csv", "json")))
    app.exporter(dossier=str(dossier), nom="essai", formats=("csv", "json"))
    attendre_calcul(app, 30)
    assert sorted(p.name for p in dossier.iterdir()) == attendus
    assert len(app.derniers_fichiers) == len(attendus) and app.prefs.dossier_export == str(dossier)
    premier = (dossier / "essai_mesures.csv").stat().st_mtime_ns
    dialogues.confirmation = False
    app.exporter(dossier=str(dossier), nom="essai", formats=("csv", "json"))
    attendre_calcul(app, 30)
    assert [q[0] for q in dialogues.questions] == ["confirmer"]
    assert (dossier / "essai_mesures.csv").stat().st_mtime_ns == premier, "refus : rien n'est remplacé"
    dialogues.confirmation = True
    app.exporter(dossier=str(dossier), nom="essai", formats=("csv", "json"))
    attendre_calcul(app, 30)
    assert len(app.derniers_fichiers) == len(attendus)
    assert app.banniere.texte.startswith(t("export.fait", n=len(attendus), dossier="")[:12])


def test_un_nom_d_export_qui_sort_du_dossier_est_refuse(app: Application, dialogues: DialoguesAutomatiques) -> None:
    calculer(app)
    app.exporter(dossier=dialogues.dossier, nom="../evasion", formats=("csv",))
    attendre_calcul(app, 30)
    assert app.derniers_fichiers == [] or all(
        Path(f).parent == Path(dialogues.dossier).resolve() for f in app.derniers_fichiers
    )
    assert not (Path(dialogues.dossier).parent / "evasion_mesures.csv").exists()


# ====================================================================
# Affichage : thème, taille, langue, journal
# ====================================================================
def test_le_theme_sombre_et_la_taille_du_texte_se_reappliquent(app: Application) -> None:
    app.definir_theme("sombre")
    assert theme.couleurs() == theme.PALETTES["sombre"] and app.prefs.theme == "sombre"
    assert ttk.Style(app).lookup("TFrame", "background") == theme.PALETTES["sombre"].fond
    assert app.menus.theme.get() == "sombre"
    app.definir_theme("clair")
    assert ttk.Style(app).lookup("TFrame", "background") == theme.PALETTES["clair"].fond
    app.police_plus()
    assert app.prefs.taille_police == 110 and tkfont.nametofont("AppCorps", root=app).cget("size") == 11
    assert str(ttk.Style(app).lookup("Treeview", "rowheight")) == str(theme.taille_police(theme.HAUTEUR_LIGNE, 110))
    for _ in range(10):
        app.police_moins()
    assert app.prefs.taille_police == preferences.TAILLE_MIN == 80
    app.police_normale()
    assert tkfont.nametofont("AppCorps", root=app).cget("size") == 10


def test_changer_de_langue_garde_les_entrees_et_le_resultat(app: Application) -> None:
    if len(textes.LANGUES) < 2:
        pytest.skip("une seule langue à ce niveau")
    champ = champ_numerique(app)
    a, _ = deux_valeurs_valides(champ)
    app.corps.formulaire.definir({champ.nom: a})
    calculer(app)
    avant = app.resultat
    app.definir_langue("en")
    assert app.langue == "en" and app.prefs.langue == "en"
    assert app.menus.barre.entrycget(0, "label") == "File"
    assert app.corps.formulaire.valider()[champ.nom] == a and app.resultat is avant
    assert any(champ.libelle_dans("en") in str(w.cget("text")) for w in _etiquettes(app.corps.formulaire))
    app.definir_langue("fr")
    assert app.menus.barre.entrycget(0, "label") == "Fichier"


def _etiquettes(racine: tk.Misc) -> Iterator[ttk.Label]:
    for enfant in racine.winfo_children():
        if isinstance(enfant, ttk.Label):
            yield enfant
        yield from _etiquettes(enfant)


def test_le_journal_visible_se_montre_se_cache_et_se_remplit(app: Application) -> None:
    app.afficher_journal(False)
    assert app.cadre_journal.winfo_manager() == "" and app.prefs.journal_visible is False
    app.basculer_journal()
    assert app.cadre_journal.winfo_manager() == "grid" and app.menus.journal.get() is True
    logging.getLogger("codap_c_97_jupe_fond.test").warning("ligne visible de test")
    app._verser_journal()
    assert "ligne visible de test" in app.zone_journal.contenu()
    app.definir_langue("fr")  # sans effet, mais la fenêtre peut se reconstruire : l'historique reste
    app._construire()
    assert "ligne visible de test" in app.zone_journal.contenu()


def test_une_exception_non_attrapee_est_montree_dans_le_bandeau(app: Application) -> None:
    journal.incidents.put("ValueError : motif de l'incident")
    app._sonder_journal()
    assert "motif de l'incident" in app.banniere.texte
    app.report_callback_exception(ZeroDivisionError, ZeroDivisionError("rappel"), None)
    assert isinstance(app.erreurs_de_rappel[-1], ZeroDivisionError) and "rappel" in app.banniere.texte


# ====================================================================
# Menus, raccourcis, navigation
# ====================================================================
def test_la_barre_de_menus_a_fichier_affichage_et_aide(app: Application) -> None:
    barre = app.menus.barre
    assert barre.index("end") == 2
    assert [barre.entrycget(k, "label") for k in range(3)] == [t("menu.fichier"), t("menu.affichage"), t("menu.aide")]
    fichier = barre.nametowidget(barre.entrycget(0, "menu"))
    libelles = [
        fichier.entrycget(k, "label") for k in range(fichier.index("end") + 1) if fichier.type(k) != "separator"
    ]
    assert t("menu.ouvrir") in libelles and t("menu.quitter") in libelles and t("menu.recents") in libelles
    assert fichier.entrycget(0, "accelerator").endswith("O")


def test_chaque_raccourci_declare_est_lie_a_une_action(app: Application) -> None:
    declares = set(app.raccourcis)
    assert declares <= set(app.liaisons) and declares <= set(app.actions)
    for nom, sequences in app.liaisons.items():
        for sequence in sequences:
            assert app.bind_all(sequence), f"{nom} : {sequence} n'est pas lié"
    chiffres = {n for n in app.liaisons if n.startswith("ecran_")}
    assert chiffres == {f"ecran_{k}" for k in range(1, app.corps.nombre_ecrans + 1)}


def test_un_raccourci_clavier_lance_son_action(app: Application, dialogues: DialoguesAutomatiques) -> None:
    app.deiconify()
    app.update()
    app.focus_force()
    app.event_generate("<F1>")
    app.update()
    assert [q[0] for q in dialogues.questions] == ["info"], "F1 ouvre le guide rapide"
    app.event_generate("<Control-plus>")
    app.update()
    assert app.prefs.taille_police == 110


def test_navigation_selon_le_style(app: Application) -> None:
    if app.style == "un":
        assert app.corps.nombre_ecrans == 0
        app.corps.afficher(3)
        app.corps.suivant()  # sans objet, sans erreur
        return
    corps = app.corps
    assert corps.courant == 0 and str(corps._rail[0].cget("style")) == "RailActif.TButton"
    if app.style == "parcours":
        assert not corps.accessible(1) and not corps.accessible(2)
        corps.afficher(1)
        assert corps.courant == 0 and app.banniere.texte == t("rail.verrouille"), (
            "écran verrouillé tant qu'aucun calcul"
        )
        assert str(corps._rail[1].cget("state")) == "disabled"
        calculer(app)
        assert corps.courant == 1, "après le calcul, on passe aux résultats"
        assert all(corps.accessible(k) for k in range(corps.nombre_ecrans))
    else:
        assert all(corps.accessible(k) for k in range(corps.nombre_ecrans)), "onglets : tout est ouvert dès le départ"
        corps.afficher(2)
        assert corps.courant == 2
    corps.afficher(1)
    corps.suivant()
    assert corps.courant == 2
    corps.precedent()
    assert corps.courant == 1
    corps.afficher(0)
    corps.precedent()  # au début : sans effet
    corps.afficher(99)  # hors rail : ignoré
    assert corps.courant == 0
    assert (
        str(corps._rail[0].cget("style")) == "RailActif.TButton" and str(corps._rail[1].cget("style")) == "Rail.TButton"
    )


def test_les_raccourcis_de_navigation_ouvrent_les_ecrans(app: Application) -> None:
    if app.style != "onglets":
        pytest.skip("navigation libre : style onglets seulement")
    app.deiconify()
    app.update()
    app.focus_force()
    app.event_generate("<Control-Key-3>")
    app.update()
    assert app.corps.courant == 2
    app.event_generate("<Alt-Left>")
    app.update()
    assert app.corps.courant == 1


# ====================================================================
# Aide, molette, fermeture
# ====================================================================
def test_aide_a_propos_diagnostic_et_pages_web(app: Application, dialogues: DialoguesAutomatiques) -> None:
    app.afficher_guide()
    app.a_propos()
    assert [q[0] for q in dialogues.questions] == ["info", "info"]
    assert __version__ in dialogues.questions[1][1]
    app.copier_diagnostic()
    assert __version__ in app.clipboard_get() and "Tk " in app.clipboard_get()
    assert app.pages == []
    app.nouvelle_version()
    assert app.pages == [URL_RELEASES]


def test_la_molette_fait_defiler_la_zone(app: Application) -> None:
    zone = ScrollableFrame(app)
    zone.place(x=0, y=0, width=200, height=100)
    for k in range(40):
        ttk.Label(zone.interieur, text=f"ligne {k}").grid(row=k, column=0)
    app.update()
    assert zone.toile.yview()[0] == 0.0
    zone.defiler(SimpleNamespace(num=5, delta=0))
    app.update()
    assert zone.toile.yview()[0] > 0.0
    zone.defiler(SimpleNamespace(num=4, delta=0))
    app.update()
    assert zone.toile.yview()[0] == 0.0
    court = ScrollableFrame(app)
    court.place(x=0, y=120, width=200, height=100)
    ttk.Label(court.interieur, text="seule ligne").grid()
    app.update()
    court.defiler(SimpleNamespace(num=5, delta=0))
    assert court.toile.yview() == (0.0, 1.0), "rien ne défile si tout est visible"


def test_quitter_garde_les_preferences_et_arrete_la_fenetre(app: Application) -> None:
    app.definir_theme("sombre")
    champ = champ_numerique(app)
    app.corps.formulaire.definir({champ.nom: deux_valeurs_valides(champ)[1]})
    app.quitter()
    relues = preferences.charger()
    assert (relues.theme, relues.taille_police) == ("sombre", 100)
    assert relues.langue == textes.langue()
    with pytest.raises(tk.TclError):
        app.winfo_exists()
        app.title()


# ====================================================================
# Verrou fin des étapes (parcours)
# ====================================================================
def test_une_etape_exige_une_etape_precise_et_le_bandeau_la_nomme(app: Application) -> None:
    if app.style != "parcours" or app.corps.nombre_ecrans < 3:
        pytest.skip("verrou fin : style parcours à trois écrans au moins")
    corps = app.corps
    calculer(app)
    derniere, precedente = corps.nombre_ecrans - 1, corps.nombre_ecrans - 2
    corps.exigences[derniere] = (precedente,)
    corps.ecrans[precedente].accompli = lambda: False  # type: ignore[method-assign]
    corps.afficher(0)
    corps.afficher(derniere)
    assert corps.courant == 0, "l'étape reste fermée tant que l'étape exigée n'est pas faite"
    assert app.banniere.texte == t("rail.verrouille_etape", etape=corps.libelle_ecran(precedente))
    assert str(corps._rail[derniere].cget("state")) == "disabled"
    corps.ecrans[precedente].accompli = lambda: True  # type: ignore[method-assign]
    corps.afficher(derniere)
    assert corps.courant == derniere


def test_une_etape_a_sa_propre_condition_et_son_message(app: Application) -> None:
    if app.style != "parcours":
        pytest.skip("style parcours seulement")
    corps = app.corps
    calculer(app)
    ecran = corps.ecrans[1]
    ecran.accessible = lambda: False  # type: ignore[method-assign]
    ecran.MESSAGE_VERROU = "rail.verrouille"
    corps.afficher(0)
    corps.afficher(1)
    assert corps.courant == 0 and app.banniere.texte == t("rail.verrouille")


def test_apres_le_calcul_la_fenetre_ouvre_l_ecran_designe(app: Application) -> None:
    if app.style != "parcours":
        pytest.skip("style parcours seulement")
    derniere = app.corps.nombre_ecrans - 1
    app.corps.ecrans[derniere].APRES_CALCUL = True
    calculer(app)
    assert app.corps.courant == derniere


# ====================================================================
# Entrées structurées, projet enregistré
# ====================================================================
def test_les_entrees_des_ecrans_rejoignent_le_formulaire_et_passent_la_meme_validation(
    app: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    champ = champ_numerique(app)
    a, b = deux_valeurs_valides(champ)
    app.corps.formulaire.definir({champ.nom: a})
    monkeypatch.setattr(app.corps, "saisie_structuree", lambda: {champ.nom: b})
    assert app.saisie_complete()[champ.nom] == b
    monkeypatch.setattr(app.corps, "saisie_structuree", lambda: {"inconnue_de_l_application": 1})
    app.calculer()
    assert app.resultat is None and not app.occupe and app.banniere.visible


def test_un_projet_enregistre_garde_l_etat_des_ecrans_et_relance_le_calcul(
    app: Application, dialogues: DialoguesAutomatiques, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    calculer(app)
    monkeypatch.setattr(app.corps, "etat", lambda: {"etape": {"choix": "b"}})
    repris: list[dict] = []
    monkeypatch.setattr(app.corps, "restaurer", repris.append)
    fichier = tmp_path / "projet_enregistre.json"
    dialogues.fichier = str(fichier)
    app.enregistrer()
    contenu = json.loads(fichier.read_text(encoding="utf-8"))
    assert contenu["etat"] == {"calcule": True, "ecrans": {"etape": {"choix": "b"}}}
    app.resultat = None
    app.ouvrir()
    assert repris == [{"etape": {"choix": "b"}}]
    attendre_calcul(app, 30)
    assert app.resultat is not None, "un projet calculé se rouvre calculé"


def test_un_tableau_se_saisit_dans_une_grille_et_se_valide_avec_le_reste(app: Application) -> None:
    from codap_c_97_jupe_fond.ui.formulaire import Formulaire

    colonnes = (
        Champ("nom", "texte", defaut="X", libelle={"fr": "Nom", "en": "Name"}),
        Champ("bas", "reel", defaut=0.0, minimum=0.0, unite="mm", libelle={"fr": "Bas", "en": "Low"}),
    )
    tableau = Champ(
        "facteurs", "tableau", defaut=[["A", 1.0]], colonnes=colonnes, lignes_min=1, lignes_max=2,
        libelle={"fr": "Facteurs", "en": "Factors"}, aide={"fr": "Un par ligne.", "en": "One per row."},
    )  # fmt: skip
    cache = Champ("interne", "reel", defaut=1.0, formulaire=False, libelle={"fr": "Interne", "en": "Internal"})
    formulaire = Formulaire(app, (tableau, cache))
    grille = formulaire.grilles["facteurs"]
    assert "interne" not in formulaire.widgets, "une entrée d'écran dédié n'est pas dans le formulaire"
    assert formulaire.valider() == {"facteurs": [{"nom": "A", "bas": 1.0}]}
    grille.ajouter_ligne(["B", "2,5"])
    assert str(grille.ajout.cget("state")) == "disabled", "deux lignes au plus"
    assert formulaire.valider()["facteurs"][1] == {"nom": "B", "bas": 2.5}
    grille.definir([{"nom": "C", "bas": -1}])
    assert str(grille.retrait.cget("state")) == "disabled", "une ligne au moins"
    with pytest.raises(ErreurSaisie):
        formulaire.valider()
    assert "ligne 1" in formulaire.message("facteurs")
    formulaire.basculer(True)
    assert str(grille.ajout.cget("state")) == "disabled"
    formulaire.basculer(False)
    grille.retirer_ligne()  # au minimum : sans effet
    assert len(grille.brut()) == 1


# ====================================================================
# Figures : enregistrement en image, thème
# ====================================================================
def _zones(app: Application) -> list:
    from codap_c_97_jupe_fond.essai import zones_de_figure

    return zones_de_figure(app)


def test_une_figure_s_enregistre_en_png_ou_en_svg_par_le_dialogue(
    app: Application, dialogues: DialoguesAutomatiques, tmp_path: Path
) -> None:
    calculer(app)
    if not app.resultat.figures:
        pytest.skip("ce calcul ne rend aucune figure")
    app.corps.afficher_resultat()
    zone = _zones(app)[0]
    assert zone.bouton is not None and zone.bouton.cget("text") == t("image.enregistrer")
    dialogues.fichier = str(tmp_path / "courbe.svg")
    zone.bouton.invoke()
    assert (tmp_path / "courbe.svg").read_bytes().startswith(b"<?xml")
    assert dialogues.questions[-1] == ("enregistrer", t("image.titre"))
    assert app.banniere.texte == t("image.enregistree", nom="courbe.svg")
    assert app.enregistrer_figure(zone.figure, tmp_path / "courbe.jpg") is None and app.banniere.niveau == "bloquant"
    dialogues.fichier = ""
    assert app.enregistrer_figure(zone.figure) is None, "dialogue abandonné : rien n'est écrit"


def test_les_figures_sont_retracees_au_changement_de_theme(app: Application) -> None:
    from matplotlib.colors import to_hex

    calculer(app)
    if not app.resultat.figures:
        pytest.skip("ce calcul ne rend aucune figure")
    app.definir_theme("sombre")
    zone = _zones(app)[0]
    assert zone.affichee is not zone.figure
    assert to_hex(zone.affichee.get_facecolor()).upper() == theme.PALETTES["sombre"].carte
    assert to_hex(zone.figure.get_facecolor()).upper() == "#FFFFFF", "la figure exportée reste claire"
    app.definir_theme("clair")
    assert _zones(app)[0].affichee is _zones(app)[0].figure


# ====================================================================
# Hauteur utile : journal replié
# ====================================================================
def test_le_journal_replie_laisse_la_zone_centrale_haute(app: Application) -> None:
    assert app.prefs.journal_replie and app.zone_journal.replie
    assert int(app.zone_journal.texte.cget("height")) == 1
    assert app.bouton_journal.cget("text") == t("journal.deplier")
    app.geometry("1180x640")
    app.update()
    replie = app.corps.winfo_height()
    assert replie >= 0.6 * app.winfo_height(), f"zone centrale {replie} px sur {app.winfo_height()} px"
    app.basculer_repli_journal()
    app.update()
    assert int(app.zone_journal.texte.cget("height")) == app.zone_journal.hauteur
    assert app.bouton_journal.cget("text") == t("journal.replier") and app.prefs.journal_replie is False
    assert app.corps.winfo_height() < replie


# ====================================================================
# Tâche propre d'une étape (une analyse), jouée par l'essai -t
# ====================================================================
def test_l_essai_joue_la_tache_propre_de_chaque_etape(app: Application) -> None:
    from codap_c_97_jupe_fond.essai import jouer_les_etapes

    if app.style == "un":
        pytest.skip("un seul écran : aucune étape")
    calculer(app)
    faites: list[str] = []
    ecran = app.corps.ecrans[-1]

    def lancer() -> bool:
        app.executer(lambda _annulation, _avancer: "analyse", nom="analyse", au_succes=faites.append)
        return True

    ecran.lancer = lancer  # type: ignore[method-assign]
    # les écrans Classeur et Étude ont leur propre tâche, plus l'étape remplacée ici
    assert jouer_les_etapes(app) == 3 and faites == ["analyse"]

    def echouer() -> bool:
        app.executer(lambda _annulation, _avancer: 1 / 0, nom="analyse", au_succes=faites.append)
        return True

    ecran.lancer = echouer  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="a échoué"):
        jouer_les_etapes(app)
