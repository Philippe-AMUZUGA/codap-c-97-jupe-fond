"""Amorce du lanceur de l'application : toute la logique de lancement (bibliothèque standard seule).

Rôle : trouver un Python accepté, préparer l'environnement local `.runtime` (créé au premier lancement,
réutilisé ensuite), lancer l'application. Les fichiers `Lancer_*.bat` et `lancer_*.sh` ne font que
trouver Python et appeler ce fichier.

Principes (décisions 1 à 5 de la conception) :
  - l'environnement n'est réutilisé que si le marqueur `INSTALLATION_OK.json` existe et correspond à
    l'empreinte de `requirements.txt` : il est écrit en dernier, après pip et après l'import de chaque
    dépendance. Au moindre échec, y compris Ctrl+C, `.runtime` est supprimé : jamais d'environnement
    à moitié installé réutilisé ;
  - pip est piloté par variables d'environnement `PIP_*` (aucune option longue dans les fichiers livrés) ;
  - si le dossier `vendor/wheels` ou `roues` contient des roues, l'installation se fait sans index (hors ligne) ;
  - repli automatique de l'environnement vers le dossier de données de l'utilisateur quand le chemin est
    long (Windows), synchronisé en ligne (OneDrive) ou non inscriptible ;
  - tout est écrit en français dans la console ; en cas d'erreur la fenêtre reste ouverte (pause) ;
    le détail est dans le journal `lanceur.log` (dossier de données locales, sous `journaux`).

Options propres au lanceur, à placer avant celles de l'application (les autres passent telles quelles) :
  -u  retirer l'environnement local (désinstallation propre)      -U  idem, et supprimer aussi les données
  -i  installer seulement, sans lancer                            -f  forcer la réinstallation
  -n  ne pas faire de pause en cas d'erreur                       -o  installation hors ligne obligatoire

Options de l'application qui gardent la console : -t (essai), -s, -V, -v, -h.

Codes de sortie : 0 réussite ; 1 erreur inattendue ; 10 Python refusé ; 11 Tk absent ; 12 réseau ;
13 pip a échoué ; 14 import d'une dépendance impossible ; 15 verrou (installation déjà en cours) ;
16 dossier inutilisable ; 17 l'application s'est arrêtée au démarrage ; 18 suppression impossible.
Avec une option de console (-t, -V...), le code de l'application est rendu tel quel.

Variables d'environnement utiles aux essais : AMORCE_SANS_PAUSE, AMORCE_ATTENTE (secondes d'attente
du démarrage), AMORCE_ATTENTE_VERROU, AMORCE_ROUES (dossier de roues), AMORCE_PAUSE (valeur « bat » :
la pause est faite par le fichier .bat).
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 8):  # garde minimale : ce fichier doit au moins s'exprimer clairement
    sys.stdout.write("Python 3.8 ou plus récent est nécessaire pour lancer cette application.\n")
    sys.exit(10)

import contextlib
import hashlib
import json
import logging
import logging.handlers
import os
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

NOM_APP = "CODAP C9.7 Jupe-Fond"
SLUG = "CodapC97JupeFond"
SLUG_MIN = "codap-c-97-jupe-fond"
PAQUET = "codap_c_97_jupe_fond"
PY_MIN = "3.11"
PY_MAX = "3.13"

AMORCE_VERSION = "1.0"
FORMAT_MARQUEUR = 1
NOM_MARQUEUR = "INSTALLATION_OK.json"
LONGUEUR_MAX_CHEMIN = 100  # au-delà, repli (la limite de 260 est atteinte dans site-packages)
DOSSIERS_ROUES = ("vendor/wheels", "roues")
SYNCHRONISES = ("onedrive", "dropbox", "google drive", "icloud drive")
OPTIONS_LANCEUR = ("-u", "-U", "-i", "-f", "-n", "-o")
OPTIONS_CONSOLE = ("-t", "-s", "-V", "-v", "-h")
EXIGER_TK = True
ATTENTE_DEMARRAGE = 3.0
ATTENTE_VERROU = 600.0
VERROU_PERIME = 1800.0

OK, ERR_INATTENDUE, ERR_PYTHON, ERR_TK, ERR_RESEAU, ERR_PIP, ERR_IMPORT = 0, 1, 10, 11, 12, 13, 14
ERR_VERROU, ERR_DOSSIER, ERR_DEMARRAGE, ERR_SUPPRESSION = 15, 16, 17, 18

MOTS_RESEAU = (
    "connection",
    "network",
    "getaddrinfo",
    "name resolution",
    "name or service",
    "retrying",
    "timed out",
    "timeout",
    "proxy",
    "ssl",
    "max retries",
    "failed to establish",
    "unreachable",
)


class ErreurLanceur(Exception):
    """Erreur prévue : un code de sortie, un titre, des détails et des conseils pour l'utilisateur."""

    def __init__(self, code, titre, details=(), conseils=()):
        super().__init__(titre)
        self.code = code
        self.titre = titre
        self.details = list(details)
        self.conseils = list(conseils)


# ==============================================================================================
# Chemins et décisions (fonctions pures ou presque : testées une à une)
# ==============================================================================================


def _variable(env, nom):
    """Valeur d'une variable d'environnement. Windows ne distingue pas les majuscules : une copie
    en dictionnaire de os.environ les perd, d'où la recherche insensible à la casse."""
    source = os.environ if env is None else env
    valeur = source.get(nom)
    if valeur is None and os.name == "nt":
        for cle, contenu in source.items():
            if cle.upper() == nom.upper():
                return contenu
    return valeur


def dossier_personnel(env=None):
    brut = _variable(env, "USERPROFILE") if os.name == "nt" else None
    brut = brut or _variable(env, "HOME")
    return Path(brut) if brut else Path.home()


def donnees_locales(env=None):
    """Dossier des données locales (runtime de repli, journaux) : %LOCALAPPDATA%, XDG ou Library."""
    if os.name == "nt":
        brut = _variable(env, "LOCALAPPDATA")
        return Path(brut) if brut else dossier_personnel(env) / "AppData" / "Local"
    if sys.platform == "darwin":
        return dossier_personnel(env) / "Library" / "Application Support"
    brut = _variable(env, "XDG_DATA_HOME")
    return Path(brut) if brut else dossier_personnel(env) / ".local" / "share"


def donnees_itinerantes(env=None):
    """Dossier des préférences : %APPDATA%, XDG_CONFIG_HOME ou Library."""
    if os.name == "nt":
        brut = _variable(env, "APPDATA")
        return Path(brut) if brut else dossier_personnel(env) / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return dossier_personnel(env) / "Library" / "Application Support"
    brut = _variable(env, "XDG_CONFIG_HOME")
    return Path(brut) if brut else dossier_personnel(env) / ".config"


def dossier_journaux(env=None):
    return donnees_locales(env) / SLUG / "journaux"


def version_en_tuple(texte):
    """« 3.11 » ou « 3.11.4 » donne (3, 11)."""
    elements = re.findall(r"\d+", str(texte))
    if len(elements) < 2:
        raise ValueError("version illisible : %r" % (texte,))
    return int(elements[0]), int(elements[1])


def lire_plage_python(dossier_app):
    """Plage de Python acceptée, relue dans `requires-python` de pyproject.toml (source unique).

    Sans pyproject ou sans cette clé, ce sont les bornes du gabarit. Rend ((min), (max)) inclus,
    par exemple ((3, 11), (3, 13)) pour « >=3.11,<3.14 ».
    """
    minimum, maximum = version_en_tuple(PY_MIN), version_en_tuple(PY_MAX)
    try:
        texte = (Path(dossier_app) / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return minimum, maximum
    trouve = re.search(r"^\s*requires-python\s*=\s*[\"']([^\"']+)[\"']", texte, re.MULTILINE)
    if not trouve:
        return minimum, maximum
    for morceau in trouve.group(1).split(","):
        morceau = morceau.strip()
        operateur = re.match(r"(>=|<=|==|~=|>|<)\s*(.+)", morceau)
        if not operateur:
            continue
        op, valeur = operateur.groups()
        try:
            borne = version_en_tuple(valeur)
        except ValueError:
            continue
        if op in (">=", "~="):
            minimum = borne
        elif op == ">":
            minimum = (borne[0], borne[1] + 1)
        elif op == "<":
            maximum = (borne[0], borne[1] - 1) if borne[1] > 0 else (borne[0] - 1, 99)
        elif op == "<=":
            maximum = borne
        elif op == "==":
            minimum = maximum = borne
    return minimum, maximum


def empreinte_requirements(fichier):
    """SHA-256 de requirements.txt, fins de ligne normalisées (insensible à CRLF et LF)."""
    brut = Path(fichier).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(brut).hexdigest()


def noms_dependances(fichier):
    """Noms des distributions listées dans requirements.txt (options et empreintes ignorées)."""
    noms = []
    for ligne in Path(fichier).read_text(encoding="utf-8", errors="replace").splitlines():
        ligne = ligne.split("#", 1)[0].strip().rstrip("\\").strip()
        if not ligne or ligne.startswith("-"):
            continue
        nom = re.split(r"[\s;=<>!~\[@]", ligne, maxsplit=1)[0]
        if nom and nom not in noms:
            noms.append(nom)
    return noms


def noms_avec_marqueur(fichier):
    """Noms des distributions dont la ligne porte un marqueur d'environnement (`; sys_platform == 'win32'`) : pip peut
    légitimement ne pas les installer sur ce poste, leur absence n'est pas une erreur."""
    noms = []
    for ligne in Path(fichier).read_text(encoding="utf-8", errors="replace").splitlines():
        ligne = ligne.split("#", 1)[0].strip().rstrip("\\").strip()
        if ligne and not ligne.startswith("-") and ";" in ligne:
            noms.append(re.split(r"[\s;=<>!~\[@]", ligne, maxsplit=1)[0])
    return noms


def avec_empreintes(fichier):
    """Vrai si requirements.txt porte des empreintes (niveau strict) : pip les exige alors."""
    return "hash=sha256:" in Path(fichier).read_text(encoding="utf-8", errors="replace")


def est_synchronise(dossier, env=None):
    """Dossier sous OneDrive (variables d'environnement ou nom de dossier), Dropbox, iCloud, Google Drive."""
    chemin = str(Path(dossier).resolve()).lower().replace("/", os.sep)
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        valeur = _variable(env, variable)
        if not valeur:
            continue
        formes = {valeur}
        with contextlib.suppress(OSError):  # forme longue : %TEMP% et d'autres variables sont en noms courts
            formes.add(str(Path(valeur).resolve()))
        for forme in formes:
            racine = forme.lower().replace("/", os.sep).rstrip("\\/")
            if racine and (chemin == racine or chemin.startswith(racine + os.sep)):
                return True
    for partie in Path(chemin).parts:
        if partie.startswith("onedrive") or partie in SYNCHRONISES:
            return True
    return False


def est_inscriptible(dossier):
    try:
        with tempfile.TemporaryFile(dir=str(dossier)):
            return True
    except OSError:
        return False


def choisir_runtime(dossier_app, env=None, windows=None):
    """Rend (dossier de l'environnement, raison du repli ou None).

    Par défaut `<application>/.runtime`. Repli vers `<données locales>/CodapC97JupeFond/runtime-<empreinte8>`
    si le chemin dépasse 100 caractères (Windows), si le dossier est synchronisé en ligne ou s'il
    n'est pas inscriptible. Même entrée, même sortie : le choix est stable d'un lancement à l'autre.
    """
    dossier_app = Path(dossier_app).resolve()
    emplacement_normal = dossier_app / ".runtime"
    windows = (os.name == "nt") if windows is None else windows
    raison = None
    if windows and len(str(emplacement_normal)) > LONGUEUR_MAX_CHEMIN:
        raison = "chemin trop long (%d caractères, limite %d)" % (len(str(emplacement_normal)), LONGUEUR_MAX_CHEMIN)
    elif est_synchronise(dossier_app, env):
        raison = "dossier synchronisé en ligne (OneDrive ou équivalent)"
    elif not est_inscriptible(dossier_app):
        raison = "dossier de l'application non inscriptible"
    if raison is None:
        return emplacement_normal, None
    cle = str(dossier_app).lower() if os.name == "nt" else str(dossier_app)
    h8 = hashlib.sha256(cle.encode("utf-8")).hexdigest()[:8]
    repli = donnees_locales(env) / SLUG / ("runtime-" + h8)
    if windows and len(str(repli)) > LONGUEUR_MAX_CHEMIN:
        # second repli : un nom court directement dans les données locales (le slug seul peut être long) ;
        # sa longueur est validée avant l'installation (`verifier_longueur_runtime`)
        repli = donnees_locales(env) / ("r-" + h8)
    return repli, raison


def verifier_longueur_runtime(runtime, windows=None):
    """Lève ErreurLanceur si le chemin de l'environnement dépasse la limite, repli compris (Windows) :
    pip et venv échoueraient dans `site-packages`, mieux vaut le dire avant."""
    windows = (os.name == "nt") if windows is None else windows
    longueur = len(str(runtime))
    if windows and longueur > LONGUEUR_MAX_CHEMIN:
        raise ErreurLanceur(
            ERR_DOSSIER,
            "Le chemin de l'environnement local est trop long, même après repli",
            ["Chemin visé : %s (%d caractères, limite %d)." % (runtime, longueur, LONGUEUR_MAX_CHEMIN)],
            [
                "Déplacez le dossier de l'application plus près de la racine d'un disque (par exemple C:\\Apps),",
                "ou raccourcissez la variable LOCALAPPDATA ; aucun réglage système n'est modifié par ce lanceur.",
            ],
        )


def trouver_roues(dossier_app, env=None):
    """Dossier de roues locales (au moins un .whl) ou None. Variable AMORCE_ROUES prioritaire."""
    candidats = []
    force = _variable(env, "AMORCE_ROUES")
    if force:
        candidats.append(Path(force))
    candidats.extend(Path(dossier_app) / relatif for relatif in DOSSIERS_ROUES)
    for dossier in candidats:
        try:
            if dossier.is_dir() and any(dossier.glob("*.whl")):
                return dossier.resolve()
        except OSError:
            continue
    return None


def variables_pip(roues, hors_ligne, empreintes, env=None):
    """Variables PIP_* de l'installation. Aucune option longue : tout passe par l'environnement."""
    pip = {
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "PIP_NO_COLOR": "1",
        "PIP_PROGRESS_BAR": "off",
        "PIP_TIMEOUT": "30",
        "PIP_RETRIES": "2",
    }
    for nom in ("PIP_TIMEOUT", "PIP_RETRIES"):  # le réglage de l'utilisateur prime
        valeur = _variable(env, nom)
        if valeur:
            pip[nom] = valeur
    if roues is not None or hors_ligne:
        pip["PIP_NO_INDEX"] = "1"
        pip["PIP_ONLY_BINARY"] = ":all:"
    if roues is not None:
        # une adresse file:// : les espaces, accents et esperluettes du chemin ne gênent pas pip
        pip["PIP_FIND_LINKS"] = Path(roues).resolve().as_uri()
    if empreintes:
        pip["PIP_REQUIRE_HASHES"] = "1"
    return pip


def python_du_venv(runtime, graphique=False):
    if os.name == "nt":
        scripts = Path(runtime) / "Scripts"
        if graphique and (scripts / "pythonw.exe").exists():
            return scripts / "pythonw.exe"
        return scripts / "python.exe"
    return Path(runtime) / "bin" / "python"


def _forcer_suppression(fonction, chemin, *_):
    os.chmod(chemin, 0o700)
    fonction(chemin)


def supprimer_arbre(chemin, essais=3):
    """Supprime un dossier (même en lecture seule). Lève OSError si un fichier reste utilisé."""
    chemin = Path(chemin)
    if not (chemin.exists() or chemin.is_symlink()):
        return
    if chemin.is_symlink() or getattr(os.path, "isjunction", lambda _p: False)(chemin):
        chemin.unlink() if chemin.is_symlink() else os.rmdir(chemin)
        return
    dernier = None
    for _ in range(essais):
        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(chemin, onexc=_forcer_suppression)
            else:
                shutil.rmtree(chemin, onerror=_forcer_suppression)
        except OSError as exc:
            dernier = exc
            time.sleep(1.0)
        if not chemin.exists():
            return
    raise OSError("suppression impossible : %s (%s)" % (chemin, dernier))


# ==============================================================================================
# Contexte, journal, console
# ==============================================================================================


class Contexte:
    """Ce que partagent les étapes : dossiers, journal, environnement, options."""

    def __init__(self, dossier_app, env=None, options=()):
        self.env = dict(os.environ if env is None else env)
        self.dossier_app = Path(dossier_app).resolve()
        self.options = set(options)
        self.runtime, self.raison_repli = choisir_runtime(self.dossier_app, self.env)
        self.requirements = self.dossier_app / "requirements.txt"
        self.journal = None
        self.chemin_journal = None
        self.battement = None
        self.non_verifies = []

    # . journal
    def ouvrir_journal(self):
        try:
            dossier = dossier_journaux(self.env)
            dossier.mkdir(parents=True, exist_ok=True)
            self.chemin_journal = dossier / "lanceur.log"
            journal = logging.getLogger("amorce.%d" % id(self))
            journal.setLevel(logging.INFO)
            journal.propagate = False
            gestionnaire = logging.handlers.RotatingFileHandler(
                str(self.chemin_journal), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            gestionnaire.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
            journal.addHandler(gestionnaire)
            self.journal = journal
        except OSError:
            self.journal = None
            self.chemin_journal = None

    def fermer_journal(self):
        if self.journal is not None:
            for gestionnaire in list(self.journal.handlers):
                gestionnaire.close()
                self.journal.removeHandler(gestionnaire)
            self.journal = None

    def noter(self, message):
        if self.journal is not None:
            try:
                self.journal.info(message)
            except OSError:
                pass

    def dire(self, message=""):
        try:
            print(message, flush=True)
        except (UnicodeError, OSError):
            print(message.encode("ascii", "replace").decode("ascii"), flush=True)
        if message:
            self.noter(message)

    # . environnement des processus fils
    def env_enfant(self, pip=None):
        env = dict(self.env)
        for nom in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"):
            env.pop(nom, None)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONNOUSERSITE"] = "1"
        if pip:
            env.update(pip)
        return env


def _preparer_console():
    for flux in (sys.stdout, sys.stderr):
        try:
            if flux.isatty():
                flux.reconfigure(errors="replace")
            else:
                flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _faire_pause(ctx_env, options):
    if "-n" in options or ctx_env.get("AMORCE_SANS_PAUSE") or ctx_env.get("AMORCE_PAUSE") == "bat":
        return
    try:
        if sys.stdin and sys.stdin.isatty():
            input("\nAppuyez sur Entrée pour fermer cette fenêtre...")
    except (EOFError, OSError, KeyboardInterrupt):
        pass


def executer(ctx, commande, env, cwd=None, afficher=True):
    """Lance un processus, relaie sa sortie à la console et au journal. Rend (code, texte)."""
    ctx.noter("commande : " + " ".join(str(c) for c in commande))
    processus = subprocess.Popen(
        [str(c) for c in commande],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
    )
    lignes = []
    try:
        for brut in iter(processus.stdout.readline, b""):
            ligne = brut.decode("utf-8", "replace").rstrip()
            lignes.append(ligne)
            if afficher and ligne:
                ctx.dire("    " + ligne)
            elif ligne:
                ctx.noter("    " + ligne)
            if ctx.battement:
                ctx.battement()
        processus.wait()
    except BaseException:
        processus.kill()
        processus.wait()
        raise
    return processus.returncode, "\n".join(lignes)


# ==============================================================================================
# Vérification du poste
# ==============================================================================================


def verifier_python(ctx, installation):
    """Python accepté (plage de pyproject), 64 bits ; si on installe : Tk, venv et ensurepip."""
    minimum, maximum = lire_plage_python(ctx.dossier_app)
    version = sys.version_info[:2]
    plage = "%d.%d à %d.%d" % (minimum + maximum)
    ctx.noter("python %s (%s), plage acceptée %s" % (sys.version.split()[0], sys.executable, plage))
    if not (minimum <= version <= maximum):
        raise ErreurLanceur(
            ERR_PYTHON,
            "Cette version de Python n'est pas prise en charge",
            ["Version trouvée : %d.%d. Versions acceptées : %s." % (version + (plage,))],
            [
                "Installez Python %s (64 bits) depuis https://www.python.org/downloads/ ." % plage,
                "Sous Windows, laissez cochées les options « tcl/tk and IDLE » et « py launcher ».",
            ],
        )
    if struct.calcsize("P") * 8 != 64:
        raise ErreurLanceur(
            ERR_PYTHON,
            "Python 32 bits n'est pas pris en charge",
            ["Les bibliothèques de calcul ne sont fournies qu'en 64 bits."],
            ["Installez la version 64 bits depuis https://www.python.org/downloads/ ."],
        )
    if not installation:
        return
    try:
        import ensurepip  # noqa: F401
        import venv  # noqa: F401
    except ImportError:
        raise ErreurLanceur(
            ERR_PYTHON,
            "Le module de création d'environnement (venv) manque",
            ["Python est installé sans venv ou sans ensurepip."],
            [
                "Linux : installez le paquet python3-venv avec le gestionnaire de paquets de votre système.",
                "Windows : réinstallez Python depuis python.org sans retirer « pip ».",
            ],
        )
    if EXIGER_TK:
        try:
            import tkinter

            tkinter.Tcl().eval("info patchlevel")
        except Exception as exc:
            raise ErreurLanceur(
                ERR_TK,
                "La bibliothèque graphique Tk est absente de ce Python",
                ["Détail : %s" % exc],
                [
                    "Windows : relancez l'installateur de Python, choisissez « Modify » et cochez « tcl/tk and IDLE ».",
                    "Linux : installez le paquet python3-tk avec le gestionnaire de paquets de votre système.",
                    "macOS : installez python-tk (par exemple avec Homebrew) ou Python depuis python.org.",
                ],
            )


# ==============================================================================================
# Marqueur et verrou
# ==============================================================================================


def _plateforme():
    return "%s-%s" % (sys.platform, platform.machine().lower())


def lire_pyvenv(runtime):
    """Lit pyvenv.cfg du venv (dossier du Python de base, version) : pas de processus à lancer."""
    infos = {}
    try:
        texte = (Path(runtime) / "pyvenv.cfg").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return infos
    for ligne in texte.splitlines():
        cle, separateur, valeur = ligne.partition("=")
        if separateur:
            infos[cle.strip().lower()] = valeur.strip()
    return infos


def version_du_venv(runtime):
    """Version « x.y.z » du Python du venv, lue dans pyvenv.cfg, ou None."""
    infos = lire_pyvenv(runtime)
    brut = infos.get("version_info") or infos.get("version") or ""
    trouve = re.match(r"(\d+)\.(\d+)\.(\d+)", brut)
    return ".".join(trouve.groups()) if trouve else None


def verifier_marqueur(ctx, empreinte):
    """(conforme, motif) : le marqueur existe, correspond à requirements.txt, au Python et au poste."""
    runtime = ctx.runtime
    if not runtime.exists():
        return False, "premier lancement : environnement à créer"
    marqueur = runtime / NOM_MARQUEUR
    if not marqueur.is_file():
        return False, "installation précédente inachevée (marqueur absent)"
    try:
        infos = json.loads(marqueur.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "marqueur d'installation illisible"
    if infos.get("format") != FORMAT_MARQUEUR or infos.get("slug") != SLUG:
        return False, "marqueur d'une autre version du lanceur"
    if infos.get("requirements_sha256") != empreinte:
        return False, "la liste des bibliothèques (requirements.txt) a changé"
    if infos.get("plateforme") != _plateforme():
        return False, "environnement créé sur un autre système"
    vpy = python_du_venv(runtime)
    if not vpy.exists():
        return False, "interpréteur de l'environnement introuvable"
    base = lire_pyvenv(runtime).get("home")
    if not base or not Path(base).is_dir():
        return False, "le Python de base de l'environnement a disparu ou a été déplacé"
    version = version_du_venv(runtime)
    if version is None:
        return False, "pyvenv.cfg de l'environnement est illisible"
    if version.rsplit(".", 1)[0] != str(infos.get("python_mineur")):
        return False, "la version de Python de l'environnement a changé"
    # la plage acceptée peut avoir changé depuis l'installation (requires-python de pyproject.toml) : le Python de
    # l'environnement doit être dans la plage d'aujourd'hui, pas seulement identique à celui du marqueur
    minimum, maximum = lire_plage_python(ctx.dossier_app)
    if not (minimum <= version_en_tuple(version) <= maximum):
        motif = "le Python de l'environnement (%s) n'est plus dans la plage acceptée (%d.%d à %d.%d)"
        return False, motif % ((version,) + minimum + maximum)
    return True, ""


@contextlib.contextmanager
def verrou(ctx):
    """Un seul lancement installe à la fois : mkdir `.runtime.verrou`, périmé après 30 minutes."""
    chemin = ctx.runtime.parent / (ctx.runtime.name + ".verrou")
    attente_max = float(ctx.env.get("AMORCE_ATTENTE_VERROU") or ATTENTE_VERROU)
    debut, prevenu = time.monotonic(), False
    try:
        ctx.runtime.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErreurLanceur(
            ERR_DOSSIER,
            "Dossier de travail inutilisable",
            [str(exc)],
            ["Vérifiez que vous avez le droit d'écrire dans %s." % ctx.runtime.parent],
        )
    while True:
        try:
            os.mkdir(str(chemin))
            break
        except FileExistsError:
            try:
                age = time.time() - chemin.stat().st_mtime
                if age > VERROU_PERIME:
                    ctx.dire("Un ancien verrou d'installation est périmé : il est retiré.")
                    supprimer_arbre(chemin)
                    continue
            except FileNotFoundError:
                continue  # le verrou vient d'être levé : nouvel essai tout de suite
            except OSError as exc:
                # accès refusé ou retrait impossible : on ne repart pas au début de la boucle, le délai d'attente
                # (code 15) et le sommeil ci-dessous s'appliquent, sinon l'attente serait sans fin
                ctx.noter("verrou illisible ou impossible à retirer : %s" % exc)
            if not prevenu:
                ctx.dire("Une installation est déjà en cours dans une autre fenêtre : attente de sa fin...")
                prevenu = True
            if time.monotonic() - debut > attente_max:
                raise ErreurLanceur(
                    ERR_VERROU,
                    "Une autre installation est toujours en cours",
                    ["Verrou : %s" % chemin],
                    ["Fermez l'autre fenêtre d'installation, ou supprimez le dossier ci-dessus si elle est fermée."],
                )
            time.sleep(1.0)
        except OSError as exc:
            raise ErreurLanceur(
                ERR_DOSSIER,
                "Verrou d'installation impossible",
                [str(exc)],
                ["Vérifiez les droits d'écriture sur %s." % chemin.parent],
            )

    def battre():
        with contextlib.suppress(OSError):
            os.utime(str(chemin), None)

    ctx.battement = battre
    try:
        (chemin / "pid").write_text(str(os.getpid()), encoding="utf-8")
        yield
    finally:
        ctx.battement = None
        with contextlib.suppress(OSError):
            supprimer_arbre(chemin)


# ==============================================================================================
# Installation
# ==============================================================================================

SCRIPT_IMPORTS = r"""
import importlib, importlib.metadata as md, json, re, sys
import os
noms = json.loads(os.environ["AMORCE_NOMS"])
marques = json.loads(os.environ.get("AMORCE_MARQUES", "[]"))
norm =lambda n: re.sub(r"[-_.]+", "-", n).lower()
hauts = {}
for module, distributions in md.packages_distributions().items():
    for d in distributions:
        hauts.setdefault(norm(d), []).append(module)
echecs, verifies, non_verifies = [], [], []
for nom in noms:
    try:
        md.distribution(nom)
    except md.PackageNotFoundError:
        if nom in marques:  # marqueur d'environnement : pip pouvait ne pas l'installer ici
            non_verifies.append(nom)
        else:
            echecs.append("%s (distribution absente après l'installation)" % nom)
        continue
    candidats = [m for m in hauts.get(norm(nom), []) if m not in ("tests", "test", "docs")]
    prives = [m for m in candidats if not m.startswith("_")]
    candidats = prives or candidats
    if not candidats:
        # aucun module identifié dans les métadonnées : on essaie le nom lui-même ; sinon la distribution est
        # notée « non vérifiée » (jamais passée sous silence : le marqueur la liste)
        supposition = re.sub(r"[-.]+", "_", nom)
        try:
            importlib.import_module(supposition)
            verifies.append(supposition)
        except BaseException:
            non_verifies.append(nom)
        continue
    # le module qui porte le nom de la distribution doit se charger ; à défaut, au moins un des modules exposés
    attendus = [m for m in candidats if norm(m) == norm(nom)]
    erreurs = []
    if attendus:
        for module in attendus:
            try:
                importlib.import_module(module)
                verifies.append(module)
            except BaseException as exc:
                erreurs.append("%s : %s: %s" % (module, type(exc).__name__, exc))
        if erreurs:
            echecs.append("%s (%s)" % (nom, "; ".join(erreurs)))
        continue
    for module in candidats:
        try:
            importlib.import_module(module)
            verifies.append(module)
            break
        except BaseException as exc:
            erreurs.append("%s : %s: %s" % (module, type(exc).__name__, exc))
    else:
        echecs.append("%s (%s)" % (nom, "; ".join(erreurs)))
print(json.dumps({"verifies": verifies, "echecs": echecs, "non_verifies": non_verifies}))
sys.exit(1 if echecs else 0)
"""


def classer_echec_pip(ctx, sortie, roues):
    if roues is not None or "-o" in ctx.options:
        return ErreurLanceur(
            ERR_PIP,
            "L'installation hors ligne a échoué",
            [
                "Le dossier de roues %s est incomplet ou ne correspond pas à Python %d.%d."
                % ((roues or "(aucun)",) + sys.version_info[:2])
            ],
            [
                "Remplissez-le avec outils/preparer_roues.py (accès au réseau nécessaire une fois),",
                "ou retirez ce dossier pour installer depuis Internet.",
            ],
        )
    minuscule = sortie.lower()
    if any(mot in minuscule for mot in MOTS_RESEAU):
        return ErreurLanceur(
            ERR_RESEAU,
            "Le réseau est inaccessible : les bibliothèques ne peuvent pas être téléchargées",
            ["Le premier lancement a besoin d'Internet (une seule fois)."],
            [
                "Connectez-vous au réseau puis relancez ; derrière un proxy, renseignez la variable HTTPS_PROXY.",
                "Sans réseau : copiez le dossier vendor/wheels fourni avec la Release de votre système.",
            ],
        )
    return ErreurLanceur(
        ERR_PIP,
        "pip n'a pas pu installer les bibliothèques",
        ["Les dernières lignes de pip sont ci-dessus et dans le journal."],
        [
            "Vérifiez que votre version de Python est dans la plage acceptée.",
            "Si le message parle de compilation, cette version n'a pas encore de roue : essayez une autre version.",
        ],
    )


def installer(ctx, empreinte, roues):
    """Crée `.runtime`, installe, vérifie, écrit le marqueur. Tout échec supprime `.runtime`."""
    runtime = ctx.runtime
    verifier_longueur_runtime(runtime)
    reussi = False
    try:
        if runtime.exists():
            supprimer_arbre(runtime)
        ctx.dire("[2/4] Création de l'environnement local...")
        code, _ = executer(ctx, [sys.executable, "-m", "venv", runtime], ctx.env_enfant())
        vpy = python_du_venv(runtime)
        if code != 0 or not vpy.exists():
            raise ErreurLanceur(
                ERR_PYTHON,
                "L'environnement local n'a pas pu être créé",
                ["Dossier visé : %s" % runtime],
                [
                    "Linux : installez python3-venv. Windows : vérifiez que le disque n'est pas plein",
                    "et que l'antivirus ne bloque pas le dossier.",
                ],
            )
        hors_ligne = "-o" in ctx.options
        pip = variables_pip(roues, hors_ligne, avec_empreintes(ctx.requirements), ctx.env)
        if roues is not None:
            ctx.dire("[3/4] Installation des bibliothèques depuis les roues locales (hors ligne)...")
        else:
            ctx.dire("[3/4] Installation des bibliothèques par pip (première fois seulement, quelques minutes)...")
        code, sortie = executer(
            ctx, [vpy, "-m", "pip", "install", "-r", ctx.requirements], ctx.env_enfant(pip), cwd=ctx.dossier_app
        )
        if code != 0:
            raise classer_echec_pip(ctx, sortie, roues)
        ctx.dire("[4/4] Vérification des bibliothèques...")
        verifies = verifier_imports(ctx, vpy)
        _ecrire_marqueur(ctx, empreinte, vpy, verifies)
        reussi = True
        ctx.dire("Installation terminée.")
    finally:
        if not reussi:
            ctx.noter("échec : suppression de l'environnement pour ne jamais réutiliser une installation partielle")
            try:
                supprimer_arbre(runtime)
            except OSError as exc:
                ctx.dire(
                    "Attention : %s est resté en place (%s). Il sera supprimé au prochain lancement." % (runtime, exc)
                )


def verifier_imports(ctx, vpy):
    noms = noms_dependances(ctx.requirements)
    if not noms:
        return []
    env = ctx.env_enfant()
    env["MPLBACKEND"] = "Agg"
    env["AMORCE_NOMS"] = json.dumps(noms)
    env["AMORCE_MARQUES"] = json.dumps(noms_avec_marqueur(ctx.requirements))
    code, sortie = executer(ctx, [vpy, "-c", SCRIPT_IMPORTS], env, afficher=False)
    dernier = sortie.strip().splitlines()[-1] if sortie.strip() else "{}"
    try:
        bilan = json.loads(dernier)
    except ValueError:
        bilan = {"verifies": [], "echecs": [sortie.strip()[-400:] or "aucune réponse"]}
    if code != 0 or bilan.get("echecs"):
        raise ErreurLanceur(
            ERR_IMPORT,
            "Une bibliothèque installée ne se charge pas",
            ["  - " + e for e in bilan.get("echecs", [])],
            [
                "Relancez : l'environnement a été supprimé et sera recréé proprement.",
                "Si cela se reproduit, joignez le journal à votre demande d'aide.",
            ],
        )
    ctx.noter("modules vérifiés : " + ", ".join(bilan.get("verifies", [])))
    ctx.non_verifies = list(bilan.get("non_verifies", []))
    if ctx.non_verifies:
        noms = ", ".join(ctx.non_verifies)
        ctx.dire("Attention : l'import de %s n'a pas pu être vérifié (aucun module dans ses métadonnées)." % noms)
    return bilan.get("verifies", [])


def _ecrire_marqueur(ctx, empreinte, vpy, verifies):
    marqueur = ctx.runtime / NOM_MARQUEUR
    infos = {
        "format": FORMAT_MARQUEUR,
        "slug": SLUG,
        "paquet": PAQUET,
        "requirements_sha256": empreinte,
        "python": version_du_venv(ctx.runtime) or ".".join(map(str, sys.version_info[:3])),
        "python_mineur": "%d.%d" % sys.version_info[:2],
        "plateforme": _plateforme(),
        "date": datetime.now().isoformat(timespec="seconds"),
        "amorce": AMORCE_VERSION,
        "modules_verifies": verifies,
        "distributions_non_verifiees": list(getattr(ctx, "non_verifies", [])),
    }
    temporaire = marqueur.with_suffix(".tmp")
    temporaire.write_text(json.dumps(infos, indent=2), encoding="utf-8")
    os.replace(str(temporaire), str(marqueur))  # dernier geste de l'installation


# ==============================================================================================
# Lancement de l'application
# ==============================================================================================


def lancer_application(ctx, arguments):
    vpy = python_du_venv(ctx.runtime)
    env = ctx.env_enfant()
    env["PYTHONPATH"] = str(ctx.dossier_app / "src")
    commande = [vpy, "-m", PAQUET] + list(arguments)
    if any(a in OPTIONS_CONSOLE for a in arguments):
        ctx.noter("lancement en console : " + " ".join(str(c) for c in commande))
        code = subprocess.call([str(c) for c in commande], env=env, cwd=str(ctx.dossier_app))
        if code != 0:
            raise ErreurLanceur(code, "L'application a rendu le code %d" % code, [], [])
        return OK
    graphique = python_du_venv(ctx.runtime, graphique=True)
    dossier_log = dossier_journaux(ctx.env)
    sortie = None
    debut = 0
    with contextlib.suppress(OSError):
        dossier_log.mkdir(parents=True, exist_ok=True)
        fichier_log = dossier_log / "lancement.log"
        sortie = open(fichier_log, "ab")
        debut = sortie.tell()
        sortie.write(("\n=== %s ===\n" % datetime.now().isoformat(timespec="seconds")).encode("utf-8"))
        sortie.flush()
        debut = sortie.tell()
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": sortie or subprocess.DEVNULL,
        "stderr": subprocess.STDOUT if sortie else subprocess.DEVNULL,
    }
    if os.name == "nt":
        options["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    ctx.noter("lancement détaché : %s -m %s" % (graphique, PAQUET))
    processus = subprocess.Popen(
        [str(graphique), "-m", PAQUET] + list(arguments), env=env, cwd=str(ctx.dossier_app), close_fds=True, **options
    )
    limite = time.monotonic() + float(ctx.env.get("AMORCE_ATTENTE") or ATTENTE_DEMARRAGE)
    while time.monotonic() < limite and processus.poll() is None:
        time.sleep(0.1)
    code = processus.poll()
    if sortie is not None:
        sortie.close()
    if code not in (None, 0):
        trace = ""
        with contextlib.suppress(OSError), open(dossier_log / "lancement.log", "rb") as lu:
            lu.seek(debut)
            trace = lu.read().decode("utf-8", "replace").strip()
        raise ErreurLanceur(
            ERR_DEMARRAGE,
            "%s s'est arrêtée dès le démarrage (code %d)" % (NOM_APP, code),
            trace.splitlines()[-12:] or ["Aucun message n'a été écrit."],
            [
                "Relancez avec l'option -t pour voir le détail dans cette fenêtre.",
                "Joignez le journal à votre demande d'aide.",
            ],
        )
    ctx.dire("%s est lancée." % NOM_APP)
    return OK


# ==============================================================================================
# Désinstallation
# ==============================================================================================


def _sur_a_supprimer(chemin, nom_attendu=None):
    chemin = Path(chemin)
    if len(chemin.parts) < 3 or chemin == Path.home() or chemin.parent == chemin:
        return False
    return nom_attendu is None or chemin.name == nom_attendu


def desinstaller(ctx, avec_donnees):
    """Retire l'environnement local (et, avec -U, les données). Appelée sous le verrou d'installation : le verrou de cet
    environnement n'est jamais retiré ici (il le sera à la sortie du bloc qui le tient) ; un verrou d'un autre
    emplacement n'est retiré que s'il est périmé."""
    verrou_propre = ctx.runtime.parent / (ctx.runtime.name + ".verrou")
    cibles = []
    for dossier in {ctx.dossier_app / ".runtime", ctx.runtime}:
        cibles.append(dossier)
        autre = dossier.parent / (dossier.name + ".verrou")
        if autre != verrou_propre and autre.exists():
            with contextlib.suppress(OSError):
                if time.time() - autre.stat().st_mtime > VERROU_PERIME:
                    cibles.append(autre)
    ctx.dire("Retrait de l'environnement local de %s..." % NOM_APP)
    if avec_donnees:
        ctx.fermer_journal()  # le journal vit dans les données qu'on va supprimer
    try:
        for cible in cibles:
            if cible.exists() and _sur_a_supprimer(cible):
                supprimer_arbre(cible)
                ctx.dire("  retiré : %s" % cible)
        if avec_donnees:
            ctx.dire("Retrait des données et journaux de %s..." % NOM_APP)
            for dossier_utilisateur in {donnees_itinerantes(ctx.env) / SLUG, donnees_locales(ctx.env) / SLUG}:
                if dossier_utilisateur.exists() and _sur_a_supprimer(dossier_utilisateur, SLUG):
                    supprimer_arbre(dossier_utilisateur)
                    ctx.dire("  retiré : %s" % dossier_utilisateur)
    except OSError as exc:
        raise ErreurLanceur(
            ERR_SUPPRESSION,
            "Suppression impossible",
            [str(exc)],
            ["Fermez %s puis relancez la désinstallation." % NOM_APP],
        )
    ctx.dire("Terminé. Pour retirer l'application elle-même, supprimez son dossier.")
    return OK


# ==============================================================================================
# Programme principal
# ==============================================================================================


def separer_arguments(argv):
    """Sépare les options du lanceur de celles de l'application, qui passent telles quelles."""
    options, restes = set(), []
    for argument in argv:
        if argument in OPTIONS_LANCEUR:
            options.add(argument)
        else:
            restes.append(argument)
    return options, restes


def afficher_erreur(ctx, erreur):
    ctx.dire("")
    ctx.dire("=" * 70)
    ctx.dire("%s : %s" % (NOM_APP, erreur.titre))
    for ligne in erreur.details:
        ctx.dire("  " + ligne)
    if erreur.conseils:
        ctx.dire("")
        ctx.dire("Que faire :")
        for ligne in erreur.conseils:
            ctx.dire("  " + ligne)
    if ctx.chemin_journal:
        ctx.dire("")
        ctx.dire("Journal : %s" % ctx.chemin_journal)
    ctx.dire("=" * 70)


def principal(argv=None, dossier_app=None, env=None):
    """Point d'entrée. `dossier_app` : dossier de l'application (par défaut le parent d'outils/)."""
    _preparer_console()
    options, restes = separer_arguments(list(sys.argv[1:] if argv is None else argv))
    racine = Path(dossier_app) if dossier_app else Path(__file__).resolve().parent.parent
    ctx = Contexte(racine, env, options)
    ctx.ouvrir_journal()
    code = OK
    try:
        ctx.noter(
            "=== lancement de %s (amorce %s), options %s %s ===" % (NOM_APP, AMORCE_VERSION, sorted(options), restes)
        )
        if "<" in SLUG or "<" in PAQUET:
            raise ErreurLanceur(
                ERR_INATTENDUE,
                "Le gabarit du lanceur n'a pas été instancié",
                ["Les jetons du gabarit doivent être remplacés par le script de génération."],
            )
        if "-u" in options or "-U" in options:
            verrou_propre = ctx.runtime.parent / (ctx.runtime.name + ".verrou")
            if any(c.exists() for c in (ctx.dossier_app / ".runtime", ctx.runtime, verrou_propre)):
                # le retrait prend le verrou d'installation : il attend la fin d'une installation en cours (ou refuse,
                # code 15) au lieu de lui retirer l'environnement et le verrou sous les pieds
                with verrou(ctx):
                    return desinstaller(ctx, "-U" in options)
            return desinstaller(ctx, "-U" in options)
        if not ctx.requirements.is_file():
            raise ErreurLanceur(
                ERR_DOSSIER,
                "requirements.txt est introuvable",
                ["Fichier attendu : %s" % ctx.requirements],
                ["Vérifiez que le dossier de l'application est complet."],
            )
        empreinte = empreinte_requirements(ctx.requirements)
        if ctx.raison_repli:
            ctx.dire("Environnement placé hors du dossier de l'application : %s." % ctx.raison_repli)
            ctx.dire("  Emplacement : %s" % ctx.runtime)
        verifier_python(ctx, installation=False)
        with verrou(ctx):
            conforme, motif = verifier_marqueur(ctx, empreinte)
            if "-f" in options:
                conforme, motif = False, "réinstallation demandée"
            if conforme:
                ctx.noter("relance rapide : marqueur conforme")
            else:
                ctx.dire("Préparation de l'environnement : %s." % motif)
                ctx.dire("[1/4] Vérification de Python et de Tk...")
                verifier_python(ctx, installation=True)
                installer(ctx, empreinte, trouver_roues(ctx.dossier_app, ctx.env))
        if "-i" in options:
            ctx.dire("Installation prête : %s." % NOM_APP)
            return OK
        return lancer_application(ctx, restes)
    except ErreurLanceur as erreur:
        code = erreur.code
        afficher_erreur(ctx, erreur)
        return code
    except KeyboardInterrupt:
        ctx.dire("\nInterrompu : l'environnement partiel éventuel a été supprimé.")
        code = ERR_INATTENDUE
        return code
    except BaseException:
        trace = traceback.format_exc()
        ctx.noter(trace)
        afficher_erreur(
            ctx,
            ErreurLanceur(
                ERR_INATTENDUE,
                "Erreur inattendue du lanceur",
                trace.strip().splitlines()[-6:],
                ["Joignez le journal à votre demande d'aide."],
            ),
        )
        code = ERR_INATTENDUE
        return code
    finally:
        ctx.noter("fin, code de sortie %s" % code)
        ctx.fermer_journal()
        if code != OK:
            _faire_pause(ctx.env, options)


if __name__ == "__main__":
    sys.exit(principal())
