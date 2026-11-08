# Notices des dépendances

Ce fichier recense les bibliothèques tierces dont CODAP C9.7 Jupe-Fond dépend, y compris leurs dépendances indirectes, avec la licence que chacune déclare. La licence de l’application (MIT) ne remplace pas ces licences : chaque bibliothèque reste sous la sienne et son texte complet est fourni avec le paquet installé.

## Inventaire

Le tableau ci-dessous est écrit par `outils/notices_tierces.py` d’après `requirements.txt` et les métadonnées des paquets installés. Il n’est pas modifié à la main.

[//]: # (inventaire : début, ne pas modifier à la main)

| Paquet | Version | Licence | Adresse |
|:-|:-|:-|:-|
| contourpy | 1.3.3 | BSD License | https://github.com/contourpy/contourpy |
| cycler | 0.12.1 | BSD License | https://matplotlib.org/cycler/ |
| et-xmlfile | 2.0.0 | MIT License | https://foss.heptapod.net/openpyxl/et_xmlfile |
| fonttools | 4.63.0 | MIT | http://github.com/fonttools/fonttools |
| kiwisolver | 1.5.0 | BSD License | https://github.com/nucleic/kiwi |
| matplotlib | 3.11.1 | Python Software Foundation License | https://matplotlib.org |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| openpyxl | 3.1.5 | MIT License | https://openpyxl.readthedocs.io |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pandas | 3.0.5 | BSD License | https://pandas.pydata.org |
| pillow | 13.0.0 | MIT-CMU | https://python-pillow.github.io |
| pyparsing | 3.3.2 | MIT | https://github.com/pyparsing/pyparsing/ |
| python-dateutil | 2.9.0.post0 | BSD License ; Apache Software License | https://github.com/dateutil/dateutil |
| six | 1.17.0 | MIT License | https://github.com/benjaminp/six |
| tzdata | 2026.3 | Apache-2.0 | https://github.com/python/tzdata |

[//]: # (inventaire : fin)

## Mise à jour

Avant chaque Release, installez les dépendances figées dans un environnement dédié, puis lancez depuis la racine de l’application :

```powershell
python outils/notices_tierces.py
```

Le script ne se connecte à aucun service. Il signale tout paquet absent de l’environnement ou sans licence déclarée : examinez-le avant de publier. L’option `-c` contrôle seulement que le fichier est à jour (code de sortie 1 sinon). Enregistrez le fichier mis à jour dans le même commit que la version publiée.
