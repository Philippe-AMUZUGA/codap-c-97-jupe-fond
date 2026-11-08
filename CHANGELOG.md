# Historique des versions

Ce fichier suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les numéros suivent [Semantic Versioning](https://semver.org/lang/fr/).

Chaque version publiée porte une date au format AAAA-MM-JJ. Datez l’en-tête de la version au jour de la publication et conservez sa forme `## [numéro] - date` : le workflow de Release en extrait les notes.

## [Unreleased]

### Modifié

- Onglet « Comparaison EF » : l'application ne livre aucune donnée d'étude ; l'utilisateur dépose ses deux fichiers de référence (dossier affiché, ou variable `CODAPC97JUPEFOND_ETUDE`). Deux fichiers synthétiques de 24 cas sont dans `examples/etude_exemple`.
- `examples/input_EF.xlsx` remplacé par un classeur synthétique.

### Ajouté

- Document `docs/VERIFICATION_VALIDATION.md` : vérification du calcul et validation contre sept cas de référence (raccordement type C, fond elliptique).

### Corrigé

- Table C26 : terme en x³ de C9.A6.5.2.6-9 et -11 à +0,598 (la transcription portait −0,598).
- Table C92 : constante −0,039 pour δ2 = 1, alignée sur les calculs de référence ; seule σmy3 change, aucun verdict modifié sur les configurations essayées.

## [0.1.0] - 2026-10-20

### Ajouté

- Vérification C9.7.5 d'un cas unique : R1 à R7, Cij, δ1, δ2, λ1, douze contraintes, trois critères, taux et verdict par côté et en enveloppe, signalement hors domaine.
- Calcul par lot d'un classeur input_CODAP.xlsx, ou d'une géométrie EF convertie ; sortie output_CODAP.xlsx et journal.
- Comparaison à une référence EF : deux matrices de confusion contre l'EF, à partir de fichiers fournis par l'utilisateur.
- Aide : périmètre, conventions mécaniques, validation et références, en français et en anglais.
- Lanceur avec environnement local dans `.runtime`, mode d'essai `-t`, exports xlsx, csv, png et projet.json avec empreintes, journal et préférences.

[Unreleased]: https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/releases/tag/v0.1.0
