# Guide d'utilisation de CODAP C9.7 Jupe-Fond

Version 0.2.0. Interface en français par défaut, en anglais par le menu Affichage. Les trois onglets sont indépendants : un calcul fait dans l'un n'efface jamais celui d'un autre. Ctrl+1 à Ctrl+3 ouvrent l'onglet voulu, Alt+flèches passent à l'onglet voisin.

## 1. Cas unique

À gauche, les 35 grandeurs de C9.7.5, rangées en cartes (géométrie, efforts et pression, thermique, matériau et sécurité), puis le type de fond et la situation. Les valeurs de départ sont celles d'une configuration de référence (e = 5 mm, D1 = H = 700 mm, MZ = 15 kN × 2H). La virgule et le point décimaux sont acceptés ; une saisie refusée est expliquée sous le champ.

Calculer (F5) affiche à droite :

- le verdict de l'enveloppe, « TENUE : OK » ou « TENUE : non-OK », avec le taux d'utilisation ; puis le verdict et le taux de chaque côté du moment global, comprimé et tendu, et le critère déterminant ;
- un avertissement « Hors domaine » quand la configuration sort du domaine tabulé C9.A6 (0,5 ≤ δ1 ≤ 1,3 ; 30 ≤ λ1 ≤ 400) ou des conditions du raccordement C (δ2 = 1, h4 nul, D3 = D4) : le verdict est alors une extrapolation, sans valeur de vérification ;
- les mesures, puis quatre tableaux : contraintes de référence R1 à R7 (deux côtés), rapports δ1, δ2, λ1 et coefficients Cij, douze contraintes des sections 1 à 3 (deux côtés), critères C9.7.5-31 à -52 avec leur équation.

Ctrl+E exporte le résultat dans le dossier choisi : classeur xlsx, fichiers csv et projet.json (entrées et empreintes, rejouable sans fenêtre). Ctrl+S enregistre le projet, Ctrl+O le rouvre.

## 2. Classeur

Choisir un classeur xlsx (bouton « Choisir… ») ; sans choix, le classeur d'exemple livré est calculé (117 configurations de référence). Un classeur sans macro ni lien externe, de 50 Mo au plus, est accepté.

- Un classeur `input_CODAP.xlsx` (les 35 colonnes) est calculé tel quel. S'il porte les colonnes `type_fond` ou `situation`, elles priment sur les réglages de l'onglet.
- Un classeur sans colonne `eu1` est lu comme une géométrie EF (`input_EF.xlsx` : e, D1, ALPHA, Pression, F_vent, F_ext, H, R1, R2, H3, D3) et converti par la chaîne du programme d'origine : MZ = F_vent × (bras × H), matériau et thermique pris aux valeurs par défaut de la conversion, écrites au journal. Un fond GRC traité en Korbbogen ou elliptique n'a aucune valeur réglementaire.

La synthèse donne une ligne par configuration (domaine, verdict, taux, côté et critère déterminants). « Écrire output_CODAP.xlsx et le journal » écrit la sortie complète du programme d'origine et `journal_CODAP.txt` (conventions, empreinte du classeur lu, valeurs de conversion, conditions d'application) dans un dossier choisi ; un fichier existant n'est jamais remplacé.

## 3. Aide et références

Périmètre, conventions mécaniques, validation du calcul et références, à lire avant d'interpréter un verdict.

## Conventions mécaniques

FZ est positif en compression ; aucun effet de fond de la pression n'est ajouté à FZ (il est porté par C71·R1). MZ = F_vent × bras ; pour un classeur de géométrie EF, le bras vaut 2H par défaut et se règle dans l'onglet Classeur. Le fond GRC des modèles EF est traité en Korbbogen (ou elliptique) : ce traitement n'a aucune valeur réglementaire, C9.7.2.1 réservant le GRC au raccordement AB. La situation d'essai est sans effets thermiques (R5 = R6 = R7 = 0).

Périmètre : C9.7.5 complet ; C9.7.6 dans la bibliothèque de calcul, non exposé ; C9.7.7 hors périmètre ; raccordement AB non implémenté. Référence : CODAP 2015, Division 2, section C9.7 et Annexe C9.A6.

## Commandes

| Touche | Action |
|:-|:-|
| F5 | calculer le cas unique |
| Ctrl+E | exporter le cas unique |
| Ctrl+O, Ctrl+S | ouvrir, enregistrer un projet |
| Ctrl+1 à Ctrl+3 | ouvrir un onglet |
| Échap | annuler le calcul en cours, ou fermer le bandeau |
| Ctrl+J | afficher ou cacher le journal |
| Ctrl+plus, Ctrl+moins, Ctrl+0 | taille du texte |
| F1 | guide rapide |

Le menu Affichage règle aussi le thème (clair ou sombre) et la langue ; le menu Aide copie un diagnostic à joindre à un signalement.

## Mode d'essai et limites

`Lancer_CodapC97JupeFond.bat -t` joue sans geste la saisie, le calcul, l'export, les trois onglets (dont le classeur d'exemple) et rend le code 0 si tout a réussi.

Limites connues : les lecteurs d'écran sont mal servis par Tk ; aucun exécutable autonome n'est fourni ; la CI sur Linux et macOS est écrite mais n'a pas encore été exécutée.
