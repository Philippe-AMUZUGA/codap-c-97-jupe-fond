# Contribution

## Préparer le projet

Créez une branche pour une modification précise. Depuis la racine du projet, préparez un environnement de développement :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONPATH = (Join-Path $PWD 'src')
```

`requirements-dev.txt` inclut `requirements.txt`. Sous Linux et macOS : `python3 -m venv .venv`, puis `.venv/bin/python -m pip install -r requirements-dev.txt` et `export PYTHONPATH=src`. L’audit des dépendances demande en plus `pip-audit` (`python -m pip install pip-audit`).

## Ajouter un écran

Déclarez l’écran et son ordre dans `src/codap_c_97_jupe_fond/donnees/application.toml`, et les champs, unités, valeurs initiales, bornes et aides dans `entrees.toml`.


Placez les calculs dans `core/calculs.py` et leur validation dans `core/schema.py`. Gardez le noyau (`core`, `systeme`, `textes`) indépendant de Tk : un test d’architecture le vérifie. Les tâches longues passent par `core/taches.py` et `ui/worker.py` et doivent pouvoir être annulées.

Ajoutez les textes dans `textes/interface_fr.toml` et leur traduction dans `interface_en.toml` : les deux fichiers ont les mêmes clés et les mêmes champs `{...}`. Ajoutez un exemple valide et un test de calcul, de validation et d’export adapté au nouvel écran. Vérifiez le focus, les unités et l’annulation dans l’interface.

## Vérifications

Exécutez les commandes suivantes depuis la racine :

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'src')
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m codap_c_97_jupe_fond -t
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
.\Lancer_CodapC97JupeFond.bat -t
```

Chaque commande doit se terminer avec un code nul. Arrêtez la vérification au premier échec. Les tests d’interface sont sautés sans écran ; ouvrez aussi l’application et vérifiez le nouvel écran à la main.

## Style et sources

Suivez `pyproject.toml` pour ruff, les imports et la longueur des lignes. Utilisez des noms de variables français sans accent. Écrivez les commentaires, aides et messages en français accentué, avec des phrases courtes. N’utilisez aucun tiret long (cadratin ou demi-cadratin) ni suite de deux traits d’union dans les textes : deux-points pour un titre, virgules pour une incise.


## Proposer une modification

Décrivez le problème, le comportement obtenu et les vérifications réalisées dans la demande de fusion. Actualisez le guide et la section `Unreleased` du [CHANGELOG](CHANGELOG.md). N’ajoutez ni données personnelles, ni environnement Python, ni journal local.

Pour une faille, utilisez le [signalement privé](SECURITY.md) avant toute discussion publique.
