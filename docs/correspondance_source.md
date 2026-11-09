# Correspondance avec le programme d'origine

Le calcul C9.7.5 n'est pas traduit : le programme d'origine (paquet `codap_c97`, `Preprocess.py` et ses 45 tests) est copié sans modification dans `src/codap_c_97_jupe_fond/core/source/`, avec l'empreinte SHA-256 de chaque fichier dans `EMPREINTES.json`. `core/calculs.py` l'appelle (`run_c975`, `convert_ef_to_codap`, `read_input_codap`, `write_output_codap`) et range ce qu'il rend en mesures, tableaux et figures. Tolérance de parité : rtol 1e-9, atol 1e-12 (`tests/golden/golden.json`).

| Élément | Origine | Statut | Motif |
|:-|:-|:-|:-|
| Verdicts, taux, côté et critère déterminants (enveloppe) | `runner.run_c975`, `synthese` | vérifié | `tests/test_parite_source.py` : appel direct et golden, six cas |
| Verdict, taux et critère de chaque côté | `run_c975`, `sides[k].adm` | vérifié | idem |
| Domaine d'application, domaine C9.A6, interaction | `run_c975`, `synthese` | vérifié | idem |
| R1 à R7, deux côtés | `run_c975`, `sides[k].R` | vérifié | idem |
| δ1, δ2, λ1 et coefficients Cij | `run_c975`, `Cij` | vérifié | idem |
| Douze contraintes des sections 1 à 3 | `run_c975`, `sides[k].stresses` | vérifié | idem |
| Critères C9.7.5-31 à -52 et leurs équations | `run_c975`, `sides[k].adm`, `_adm_obj.equations` | vérifié | idem |
| Classeur `input_CODAP.xlsx` calculé par lot, `output_CODAP.xlsx` | `io_excel.read_input_codap`, `run_c975`, `io_excel.write_output_codap` | vérifié | `tests/test_calculs.py` (117 configurations) et tests d'origine `test_io_and_pipeline` |
| Conversion d'une géométrie EF | `Preprocess.convert_ef_to_codap` | vérifié | tests d'origine `test_io_and_pipeline` ; `tests/test_calculs.py` |
| C9.7.6 (stabilité de la jupe) | `codap_c97/stability.py` | non intégrée | disponible dans la bibliothèque et couverte par ses tests d'origine, non exposée dans l'interface (hors du périmètre demandé) |
| C9.7.7, raccordement AB | absents du programme d'origine | non traduit | hors périmètre du programme d'origine |

Les docstrings historiques de `Preprocess.py` décrivent encore une ancienne convention de signe ; le code exécuté applique FZ positif en compression et n'ajoute pas l'effet de fond à FZ : l'interface, le guide et le README décrivent la convention exécutée.
