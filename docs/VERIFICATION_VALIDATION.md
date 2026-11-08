# Vérification et validation

Ce document décrit comment le calcul C9.7.5 a été vérifié (réalise-t-on bien ce que dit le CODAP ?) et validé (retrouve-t-on les résultats d'outils de référence ?). Les chiffres sont reproductibles avec `tests/` et l'onglet « Comparaison EF ».

## Vérification

| Contrôle | Méthode | Résultat |
|:-|:-|:-|
| Tests du programme | 45 tests unitaires et de chaîne | 45 réussis |
| Coefficients tabulés du fond elliptique | confrontation à un programme historique de 2022, 117 configurations, tolérance 1e-12 | 27 sur 28 identiques ; C92 diffère volontairement (voir plus bas) |
| Chaîne R1 à R7, 12 contraintes, critères C9.7.5-31 à -52 | réimplémentation indépendante écrite à partir des seules pages du CODAP, plus de 900 configurations × 2 côtés | écart relatif maximal 9e-13, verdicts identiques |
| Tables C9.A6.5 | relecture des 1 898 valeurs contre les pages imprimées, chaque écart revérifié par agrandissement | une erreur de signe corrigée (C26, terme en x³, +0,598) |
| Équation C9.7.5-2 | relecture de la page | facteur 2 de R2 = 2 FZ / (π D3 eu1) confirmé |

## Validation contre des calculs de référence

Sept cas de raccordement type C (appareil posé sur la jupe) à fond elliptique : cinq calculés par un logiciel spécialisé du commerce, deux issus d'une note de calcul indépendante. Pour chaque cas, 41 coefficients Cij, les contraintes R1 à R7 et les douze contraintes des trois sections critiques (côtés comprimé et tendu) sont comparés aux valeurs imprimées par l'outil de référence ; tolérance : précision d'impression (écart absolu 2e-3 ou relatif 1e-3).

| Famille de cas | Concordance |
|:-|:-|
| δ1 = eu3/eu1 ≤ 1 (6 cas, δ1 de 0,645 à 0,784) | tous les Cij, R1 à R7 et contraintes concordent ; section critique, σmV et v2 identiques ; écart relatif maximal 1,4e-4 sur les contraintes |
| δ1 = 1,10 (1 cas, tranche ]1,0 ; 1,2] des coefficients) | six coefficients (C21, C31, C51, C61, C81, C91) s'écartent de 0,6 % à 2,9 % ; contraintes de flexion écartées de 2,4 % au plus ; verdict identique |

Les sept cas sont non conformes (σmx1 et σbx1 au-delà des limites) chez l'outil de référence comme dans ce programme : les verdicts sont identiques. Aucun cas de référence n'est conforme : le côté admissible est validé par la réimplémentation indépendante et par la concordance des contraintes.

### Points d'attention

- **Tranche ]1,0 ; 1,2] de δ1.** Aux deux bornes, le programme et l'outil de référence donnent la même valeur à δ1 = 1,0 ; ils diffèrent à δ1 = 1,2. Le polynôme que l'outil utilise à cette borne ne figure pas dans le texte du CODAP 2015 que le programme transcrit (une révision postérieure en est la cause probable, non vérifiée). Les configurations à δ1 = 1 ne sont pas concernées.
- **Coefficient C92.** Le texte imprimé du CODAP 2015 se contredit (C9.A6.5.9.2-3 et -5 : +0,039 et +0,056 ; -21, -23 et -25 : -0,056, -0,039 et -0,056). Pour δ2 = 1, le programme emploie la constante −0,039, retenue par l'outil de référence et par la note de calcul indépendante. Seule σmy3 change (0,2 à 0,9 MPa) ; aucun verdict de l'étude n'est modifié pour le fond Korbbogen à bras de levier 2H.
- **Membrane saturée (v2 > 1).** L'outil de référence imprime des valeurs formelles de k1 et σball (négatives) ; le programme retourne σball = 0 et signale « hors domaine ». Le verdict est le même : convention différente, non écart de calcul.

## Limites

Aucun cas de référence avec fond Korbbogen ou GRC, avec δ2 ≠ 1 (raccordement type AB, non implémenté), avec δ1 > 1,1 ou 0,8 < δ1 < 1. La stabilité de la jupe (C9.7.6) et l'ancrage (C9.7.7) ne sont pas comparés.
