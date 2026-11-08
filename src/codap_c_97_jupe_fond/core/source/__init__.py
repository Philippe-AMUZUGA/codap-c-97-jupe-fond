"""
Programme de calcul d'origine, copié tel quel (jamais réécrit ni reformaté), avec l'empreinte SHA-256 de chaque fichier.

`codap_c97/` : la vérification C9.7.5 (coefficients C9.A6, contraintes, critères, conditions d'application, lecture et
écriture des classeurs) ; `Preprocess.py` : la conversion d'un classeur de géométrie EF en classeur d'entrée ;
`tests/` : les 45 tests du programme d'origine, rejoués par `tests/test_noyau_origine.py` de l'application, avec
`temoin/` : le programme historique de 2022 qui sert de témoin de non-régression à ces tests (texte, jamais importé).
`EMPREINTES.json` donne l'empreinte de chaque fichier (fins de ligne ramenées à LF pour un fichier texte) :
`tests/test_parite_source.py` la relit et échoue si un fichier a changé.
"""
