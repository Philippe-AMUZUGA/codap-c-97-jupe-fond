"""Parties de l'interface qui se testent sans écran : molette, raccourcis, messages d'erreur, pilote de calcul."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import pytest

from codap_c_97_jupe_fond import textes
from codap_c_97_jupe_fond.core.erreurs import ErreurAnnulation, ErreurApplication, ErreurCalcul, ErreurSaisie
from codap_c_97_jupe_fond.core.taches import Progression
from codap_c_97_jupe_fond.ui.menus import decrire_raccourci
from codap_c_97_jupe_fond.ui.widgets import pas_de_molette
from codap_c_97_jupe_fond.ui.worker import Pilote, message_d_erreur


# ====================================================================
# Molette
# ====================================================================
@pytest.mark.parametrize(
    ("delta", "plateforme", "attendu"),
    [
        (120, "win32", -1),
        (-120, "win32", 1),
        (240, "win32", -2),
        (30, "win32", -1),  # pavé tactile à haute résolution : au moins un cran
        (-30, "win32", 1),
        (120, "linux", -1),
        (3, "darwin", -3),
        (-1, "darwin", 1),
        (0, "win32", 0),
    ],
)
def test_pas_de_molette(delta: int, plateforme: str, attendu: int) -> None:
    assert pas_de_molette(delta, plateforme) == attendu


# ====================================================================
# Raccourcis
# ====================================================================
def test_un_raccourci_avec_modificateur_et_lettre() -> None:
    assert decrire_raccourci("Mod+o", "win32") == (["<Control-o>", "<Control-O>"], "Ctrl+O")
    assert decrire_raccourci("Mod+o", "darwin") == (["<Command-o>", "<Command-O>"], "Cmd+O")


def test_les_touches_speciales_et_de_fonction() -> None:
    assert decrire_raccourci("F5") == (["<F5>"], "F5")
    assert decrire_raccourci("Escape") == (["<Escape>"], "Esc")
    assert decrire_raccourci("Alt+Left") == (["<Alt-Left>"], "Alt+←")


def test_plus_et_moins_couvrent_les_claviers_courants() -> None:
    plus, libelle = decrire_raccourci("Mod+plus", "win32")
    assert {"<Control-plus>", "<Control-equal>", "<Control-KP_Add>"} <= set(plus) and libelle == "Ctrl++"
    moins, _ = decrire_raccourci("Mod+minus", "linux")
    assert {"<Control-minus>", "<Control-KP_Subtract>"} <= set(moins)
    chiffre, libelle = decrire_raccourci("Mod+0", "win32")
    assert chiffre == ["<Control-Key-0>"] and libelle == "Ctrl+0"


# ====================================================================
# Messages d'erreur
# ====================================================================
def test_message_d_erreur_prevue_imprevue_et_annulee() -> None:
    textes.definir_langue("fr")
    assert message_d_erreur(ErreurCalcul("erreur.refus", motif="valeurs hors domaine")) == str(
        ErreurCalcul("erreur.refus", motif="valeurs hors domaine")
    )
    assert message_d_erreur(ErreurSaisie("saisie.vide", champ="Charge")).startswith("Charge")
    assert message_d_erreur(ErreurAnnulation()) == "Calcul annulé."
    imprevue = message_d_erreur(ZeroDivisionError("detail technique"), "le calcul")
    assert "ZeroDivisionError" in imprevue and "detail technique" not in imprevue and "journal" in imprevue


# ====================================================================
# Pilote, avec une fausse boucle Tk
# ====================================================================
class FausseRacine:
    """Boucle de remplacement : `after` range le rappel, `tourner` le rejoue jusqu'à épuisement."""

    def __init__(self) -> None:
        self.rappels: list[Callable[[], None]] = []

    def after(self, _ms: int, fonction: Callable[[], None]) -> None:
        self.rappels.append(fonction)

    def tourner(self, delai: float = 5.0) -> None:
        fin = time.monotonic() + delai
        while self.rappels and time.monotonic() < fin:
            self.rappels.pop(0)()
            time.sleep(0.002)
        assert not self.rappels, "le pilote ne s'est pas arrêté"


class Observateur:
    def __init__(self) -> None:
        self.progressions: list[tuple[float, str]] = []
        self.occupations: list[bool] = []
        self.succes: list[object] = []
        self.echecs: list[BaseException] = []
        self.annulations = 0


def _pilote() -> tuple[Pilote, FausseRacine, Observateur]:
    racine, obs = FausseRacine(), Observateur()
    pilote = Pilote(racine, lambda f, m: obs.progressions.append((f, m)), obs.occupations.append)  # type: ignore[arg-type]
    return pilote, racine, obs


def _lancer(pilote: Pilote, obs: Observateur, fonction) -> None:
    pilote.lancer(
        fonction,
        nom="calcul d'essai",
        au_succes=obs.succes.append,
        en_echec=obs.echecs.append,
        si_annulee=lambda: setattr(obs, "annulations", obs.annulations + 1),
    )


def test_le_pilote_rend_le_resultat_dans_la_boucle_de_tk() -> None:
    pilote, racine, obs = _pilote()

    def calcul(annulation, avancer):
        for k in range(1, 4):
            avancer(Progression("e", k, 3, f"unite {k}"))
            time.sleep(0.01)
        return "valeur"

    _lancer(pilote, obs, calcul)
    assert pilote.occupe
    racine.tourner()
    assert obs.succes == ["valeur"] and obs.echecs == [] and not pilote.occupe
    assert obs.occupations == [True, False]
    assert obs.progressions[0] == (0.0, "calcul d'essai") and obs.progressions[-1] == (0.0, "")
    assert max(f for f, _ in obs.progressions) == pytest.approx(1.0)


def test_le_pilote_refuse_un_second_calcul_pendant_le_premier() -> None:
    pilote, racine, obs = _pilote()
    _lancer(pilote, obs, lambda a, v: time.sleep(0.05))
    with pytest.raises(RuntimeError, match="déjà en cours"):
        _lancer(pilote, obs, lambda a, v: None)
    racine.tourner()


def test_le_pilote_signale_un_echec_et_journalise_la_trace(caplog: pytest.LogCaptureFixture) -> None:
    pilote, racine, obs = _pilote()

    def calcul(annulation, avancer):
        raise ZeroDivisionError("boom")

    with caplog.at_level(logging.WARNING):
        _lancer(pilote, obs, calcul)
        racine.tourner()
    assert [type(e) for e in obs.echecs] == [ZeroDivisionError] and obs.succes == []
    assert any("Traceback" in r.getMessage() and "boom" in r.getMessage() for r in caplog.records)


def test_une_erreur_prevue_n_ecrit_qu_une_ligne_sans_trace(caplog: pytest.LogCaptureFixture) -> None:
    pilote, racine, obs = _pilote()

    def calcul(annulation, avancer):
        raise ErreurCalcul("erreur.refus", motif="valeurs hors domaine")

    with caplog.at_level(logging.INFO):
        _lancer(pilote, obs, calcul)
        racine.tourner()
    assert isinstance(obs.echecs[0], ErreurApplication)
    assert not any("Traceback" in r.getMessage() for r in caplog.records)


def test_le_pilote_annule_le_calcul() -> None:
    pilote, racine, obs = _pilote()

    def calcul(annulation, avancer):
        for _ in range(1000):
            annulation.verifier()
            time.sleep(0.005)

    _lancer(pilote, obs, calcul)
    pilote.annuler()
    racine.tourner()
    assert obs.annulations == 1 and obs.succes == [] and obs.echecs == []


# ====================================================================
# Verrou fin des étapes, filtres des boîtes de fichiers
# ====================================================================
def _rail():
    """Le module du rail, absent du style « un écran » : le test est alors dit sauté."""
    return pytest.importorskip("codap_c_97_jupe_fond.ui.rail", reason="style un : pas de rail")


def _classe(cle: str, exige: tuple[str, ...] = ()) -> type:
    from codap_c_97_jupe_fond.ui.ecrans.base import Ecran

    return type(f"Ecran_{cle}", (Ecran,), {"CLE": cle, "EXIGE": exige})


def test_une_etape_exige_des_etapes_precises_placees_avant_elle() -> None:
    etapes_exigees = _rail().etapes_exigees

    declarations = [{"cle": "a"}, {"cle": "b"}, {"cle": "c", "exige": ["a", "b"]}, {"cle": "d", "exige": "b"}]
    classes = [_classe("a"), _classe("b", ("a",)), _classe("c"), _classe("d")]
    assert etapes_exigees(declarations, classes) == [(), (0,), (0, 1), (1,)], "la déclaration prime sur la classe"


@pytest.mark.parametrize(
    ("declarations", "motif"),
    [
        ([{"cle": "a", "exige": ["z"]}], "inconnue"),
        ([{"cle": "a", "exige": ["a"]}], "avant"),
        ([{"cle": "a", "exige": ["b"]}, {"cle": "b"}], "avant"),
    ],
)
def test_une_exigence_impossible_est_refusee(declarations: list, motif: str) -> None:
    etapes_exigees = _rail().etapes_exigees

    with pytest.raises(ValueError, match=motif):
        etapes_exigees(declarations, [_classe(d["cle"]) for d in declarations])


def test_les_filtres_des_boites_de_fichiers() -> None:
    from codap_c_97_jupe_fond.ui.dialogues import types_de_fichiers

    assert types_de_fichiers("image") == [("PNG", "*.png"), ("SVG", "*.svg")]
    assert types_de_fichiers("json") == [("JSON", "*.json")]
    assert types_de_fichiers("csv") == [("CSV", "*.csv")]
