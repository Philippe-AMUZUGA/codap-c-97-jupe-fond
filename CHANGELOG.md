# Historique des versions

Ce fichier suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les numéros suivent [Semantic Versioning](https://semver.org/lang/fr/).

Chaque version publiée porte une date au format AAAA-MM-JJ. Datez l’en-tête de la version au jour de la publication et conservez sa forme `## [numéro] - date` : le workflow de Release en extrait les notes.

## [Unreleased]

## [0.2.0] - 2026-11-09

### Modifié

- Trois onglets : cas unique, classeur, aide. Le classeur sert au plan d'expériences de l'utilisateur.
- Interface allégée : plus de bandeau d'aide à trois repères sur chaque écran, titres et messages raccourcis ; l'aide se lit dans le guide rapide (F1) et l'onglet Aide.
- `examples/input_EF.xlsx` remplacé par un classeur synthétique.
- Pillow 13.0.0 (correctifs de sécurité signalés par pip-audit sur 12.3.0).
- Les deux tests de raccourcis clavier sont ignorés quand la session ne donne aucun focus clavier (CI sous macOS).

### Ajouté

- Document `docs/VERIFICATION_VALIDATION.md` : vérification du calcul et validation contre sept cas de référence (raccordement type C, fond elliptique).

### Retiré

- Onglet de comparaison à une référence EF (matrices de confusion), propre à un usage de recherche : il demandait des fichiers au format d'une chaîne EF particulière.

### Corrigé

- Table C26 : terme en x³ de C9.A6.5.2.6-9 et -11 à +0,598 (la transcription portait −0,598).
- Table C92 : constante −0,039 pour δ2 = 1, alignée sur les calculs de référence ; seule σmy3 change, aucun verdict modifié sur les configurations essayées.
- Tests des raccourcis clavier : modificateur Commande sous macOS, Ctrl ailleurs (la CI macOS échouait).

## [0.1.0] - 2026-10-20

### Ajouté

- Vérification C9.7.5 d'un cas unique : R1 à R7, Cij, δ1, δ2, λ1, douze contraintes, trois critères, taux et verdict par côté et en enveloppe, signalement hors domaine.
- Calcul par lot d'un classeur input_CODAP.xlsx, ou d'une géométrie EF convertie ; sortie output_CODAP.xlsx et journal.
- Aide : périmètre, conventions mécaniques, validation et références, en français et en anglais.
- Lanceur avec environnement local dans `.runtime`, mode d'essai `-t`, exports xlsx, csv, png et projet.json avec empreintes, journal et préférences.

[Unreleased]: https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/releases/tag/v0.1.0
