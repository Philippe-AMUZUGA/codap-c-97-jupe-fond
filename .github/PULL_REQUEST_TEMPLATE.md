# Proposition de modification

## Problème et résultat

Décrivez le problème, son déclencheur et le comportement obtenu. Reliez l’issue concernée si elle existe. Pour une faille, suivez SECURITY.md avant toute description publique.

## Changements

Nommez les écrans, calculs, champs ou exports modifiés. Expliquez toute modification de format ou de dépendance et son effet sur les données existantes.

## Vérifications

Indiquez le système, la version de Python et les résultats des commandes. Cochez uniquement les contrôles exécutés avec succès.

- [ ] `python -m ruff check .`
- [ ] `python -m pytest`
- [ ] `python -m codap_c_97_jupe_fond -t`
- [ ] `Lancer_CodapC97JupeFond.bat -t` sous Windows, ou `sh lancer_codap-c-97-jupe-fond.sh -t` sous Linux et macOS.
- [ ] `python -m pip_audit -r requirements.txt`
- [ ] Interface vérifiée pour les écrans modifiés, ou absence de changement d’interface expliquée.
- [ ] Documentation et CHANGELOG actualisés si nécessaire.
- [ ] Textes en français accentué, sans tirets interdits.
- [ ] Aucune donnée personnelle ni modification non justifiée des références de `core/source`.

Décrivez les contrôles non réalisés et leur raison. Joignez une capture nettoyée si elle aide à examiner l’interface.
