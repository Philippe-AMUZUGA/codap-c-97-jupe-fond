"""Services système : chemins par plateforme, préférences, journal roulant, crochets d'exceptions, diagnostic."""

from __future__ import annotations

import json
import logging
import sys
import threading
from pathlib import Path

import pytest

from codap_c_97_jupe_fond import SLUG, __version__
from codap_c_97_jupe_fond.systeme import chemins, diagnostic, journal, preferences


# ====================================================================
# Chemins
# ====================================================================
def test_chemins_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chemins.rediriger(None)
    monkeypatch.delenv(chemins.VARIABLE_DONNEES, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert chemins.dossier_donnees(creer=False) == tmp_path / "Roaming" / SLUG
    assert chemins.dossier_journaux(creer=False) == tmp_path / "Local" / SLUG / "journaux"


def test_chemins_macos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chemins.rediriger(None)
    monkeypatch.delenv(chemins.VARIABLE_DONNEES, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert chemins.dossier_donnees(creer=False) == tmp_path / "Library" / "Application Support" / SLUG
    assert chemins.dossier_journaux(creer=False) == tmp_path / "Library" / "Logs" / SLUG


def test_chemins_linux_avec_et_sans_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chemins.rediriger(None)
    monkeypatch.delenv(chemins.VARIABLE_DONNEES, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "etat"))
    assert chemins.dossier_donnees(creer=False) == tmp_path / "cfg" / SLUG
    assert chemins.dossier_journaux(creer=False) == tmp_path / "etat" / SLUG / "journaux"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.delenv("XDG_STATE_HOME")
    assert chemins.dossier_donnees(creer=False) == tmp_path / ".config" / SLUG
    assert chemins.dossier_journaux(creer=False) == tmp_path / ".local" / "state" / SLUG / "journaux"


def test_la_redirection_et_la_variable_d_environnement_gagnent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(chemins.VARIABLE_DONNEES, str(tmp_path / "env"))
    chemins.rediriger(None)
    assert chemins.dossier_donnees() == tmp_path / "env" / "donnees"
    chemins.rediriger(tmp_path / "forcee")
    assert chemins.dossier_journaux() == tmp_path / "forcee" / "journaux"
    assert chemins.dossier_journaux().is_dir()


def test_les_ressources_se_trouvent_ou_manquent_sans_erreur() -> None:
    exemple = chemins.chemin_exemple()
    assert exemple is not None and exemple.name == "exemple.json"
    assert chemins.chemin_asset("fichier_qui_n_existe_pas.png") is None


# ====================================================================
# Préférences
# ====================================================================
def test_les_preferences_font_l_aller_retour() -> None:
    prefs = preferences.Preferences(langue="en", theme="sombre", taille_police=130, journal_visible=False)
    chemin = preferences.enregistrer(prefs)
    assert chemin.parent == chemins.dossier_donnees()
    assert preferences.charger() == prefs
    assert json.loads(chemin.read_text(encoding="utf-8"))["version_format"] == preferences.FORMAT_ACTUEL
    assert not chemin.with_name(chemin.name + ".tmp").exists()


def test_sans_fichier_les_valeurs_par_defaut() -> None:
    assert preferences.charger() == preferences.Preferences()


def test_un_fichier_illisible_est_mis_de_cote() -> None:
    chemin = chemins.fichier_preferences()
    chemin.write_text("{ pas du json", encoding="utf-8")
    assert preferences.charger() == preferences.Preferences()
    assert chemin.with_suffix(".json.corrompu").is_file() and not chemin.exists()


def test_un_ancien_format_est_migre_et_les_valeurs_hors_domaine_corrigees() -> None:
    chemin = chemins.fichier_preferences()
    chemin.write_text(json.dumps({"taille": 500, "sombre": True, "inconnue": 1, "recents": "x"}), encoding="utf-8")
    prefs = preferences.charger()
    assert prefs.version_format == preferences.FORMAT_ACTUEL
    assert (prefs.theme, prefs.taille_police, prefs.recents) == ("sombre", preferences.TAILLE_MAX, [])
    chemin.write_text(json.dumps({"version_format": 99, "theme": "rose", "taille_police": "grand"}), encoding="utf-8")
    prefs = preferences.charger()
    assert (prefs.theme, prefs.taille_police) == ("clair", 100)


def test_les_recents_sont_sans_doublon_et_limites_a_huit(tmp_path: Path) -> None:
    prefs = preferences.Preferences()
    fichiers = []
    for k in range(10):
        fichier = tmp_path / f"f{k}.json"
        fichier.write_text("{}", encoding="utf-8")
        fichiers.append(fichier)
        preferences.ajouter_recent(prefs, fichier)
    preferences.ajouter_recent(prefs, fichiers[5])
    assert len(prefs.recents) == preferences.NOMBRE_RECENTS == 8
    assert prefs.recents[0] == str(fichiers[5].resolve()) and len(set(prefs.recents)) == 8


# ====================================================================
# Journal
# ====================================================================
def test_le_journal_ecrit_un_fichier_et_alimente_le_flux_visible() -> None:
    flux = journal.installer()
    logging.getLogger("codap_c_97_jupe_fond.essai").warning("alerte de test")
    logging.getLogger("codap_c_97_jupe_fond.test").info("ligne de test")
    contenu = journal.fichier_journal().read_text(encoding="utf-8")
    assert "alerte de test" in contenu and "ligne de test" in contenu
    lignes = flux.vider()
    assert any("alerte de test" in ligne and "WARNING" in ligne for ligne in lignes)
    assert flux.vider() == []


def test_installer_deux_fois_ne_double_pas_les_lignes() -> None:
    journal.installer()
    flux = journal.installer()
    logging.getLogger("codap_c_97_jupe_fond.test").info("une seule fois")
    assert sum("une seule fois" in ligne for ligne in flux.vider()) == 1
    assert journal.fichier_journal().read_text(encoding="utf-8").count("une seule fois") == 1


def test_le_fichier_de_journal_est_roulant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal, "TAILLE_MAX_OCTETS", 2000)
    monkeypatch.setattr(journal, "SAUVEGARDES", 2)
    journal.installer()
    ecrire = logging.getLogger("codap_c_97_jupe_fond.rotation")
    for k in range(200):
        ecrire.info("ligne numero %d de remplissage du fichier", k)
    journal.desinstaller()
    dossier = journal.fichier_journal().parent
    noms = sorted(p.name for p in dossier.iterdir())
    assert noms == [journal.NOM_FICHIER, journal.NOM_FICHIER + ".1", journal.NOM_FICHIER + ".2"]
    assert all(p.stat().st_size <= 2100 for p in dossier.iterdir())


def test_les_exceptions_non_attrapees_sont_journalisees_et_signalees() -> None:
    flux = journal.installer()
    journal.poser_crochets()
    sys.excepthook(ValueError, ValueError("echec principal"), None)

    def echoue() -> None:
        raise RuntimeError("echec du fil")

    fil = threading.Thread(target=echoue, name="fil-d-essai")
    fil.start()
    fil.join()
    messages = []
    while not journal.incidents.empty():
        messages.append(journal.incidents.get_nowait())
    assert any("echec principal" in m for m in messages) and any("echec du fil" in m for m in messages)
    contenu = "\n".join(flux.vider())
    assert "exception non attrapée" in contenu and "fil-d-essai" in contenu


# ====================================================================
# Diagnostic
# ====================================================================
def test_le_diagnostic_remplace_le_dossier_personnel() -> None:
    accueil = str(Path.home())
    assert diagnostic.anonymiser(f"erreur dans {accueil}\\donnees et {accueil.replace(chr(92), '/')}/x") == (
        "erreur dans ~\\donnees et ~/x"
    )


def test_le_diagnostic_donne_la_version_sans_donnees_personnelles(tmp_path: Path) -> None:
    journal.installer()
    logging.getLogger("codap_c_97_jupe_fond.test").info("ligne pour le diagnostic")
    journal.desinstaller()
    prefs = preferences.Preferences(dossier_export=str(Path.home() / "secret"), recents=[str(Path.home() / "x.json")])
    texte = diagnostic.diagnostic(prefs, version_tk="8.6")
    assert __version__ in texte and "ligne pour le diagnostic" in texte and "Tk 8.6" in texte
    assert "secret" not in texte and "x.json" not in texte
    assert str(Path.home()) not in texte


def test_le_journal_est_replie_par_defaut_et_le_reglage_se_garde(tmp_path: Path) -> None:
    """Replié, le journal laisse sa hauteur à la zone centrale ; l'utilisateur le déplie et le choix est gardé."""
    assert preferences.Preferences().journal_replie is True
    fichier = tmp_path / "prefs.json"
    preferences.enregistrer(preferences.Preferences(journal_replie=False), fichier)
    assert preferences.charger(fichier).journal_replie is False
    fichier.write_text(json.dumps({"version_format": 1, "journal_replie": "oui"}), encoding="utf-8")
    assert preferences.charger(fichier).journal_replie is True
