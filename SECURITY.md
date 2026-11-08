# Sécurité

## Versions prises en charge

Seule la dernière version publiée reçoit des correctifs de sécurité. Les versions antérieures et les copies modifiées ne sont pas prises en charge. Mettez à jour avant de vérifier une anomalie.

## Signalement privé

Utilisez [Report a vulnerability](https://github.com/Philippe-AMUZUGA/codap-c-97-jupe-fond/security/advisories/new) dans l’onglet Security du dépôt. Le propriétaire du dépôt doit avoir activé les signalements privés de vulnérabilité (Settings, Code security, Private vulnerability reporting) ; sinon, le lien n’ouvre pas de formulaire.

N’ouvrez pas d’issue publique pour une faille. Indiquez la version, le système, les étapes, les fichiers concernés et l’impact observé. Joignez un exemple minimal sans données personnelles ni secrets. Si le formulaire privé est indisponible, n’envoyez aucun détail par un canal public et attendez qu’il soit activé.

L’auteur examine le signalement en privé, prépare le correctif et convient avec le déclarant des informations à publier. Aucun délai de réponse n’est garanti.

## Fichiers reçus et sources

L’application n’exécute que le code de ce dépôt. Elle n’interprète jamais comme du code un fichier reçu à l’exécution : classeur ou fichier d’entrées de l’utilisateur, export, saisie. Les entrées sont validées par le schéma avant tout calcul, et les exports n’écrivent que dans le dossier choisi.

Le dossier `core/source`, quand il existe, garde le fichier d’origine du calcul tel quel, avec son empreinte SHA-256 contrôlée par les tests : ne le modifiez pas pour faire passer un test. N’ajoutez ni évaluation dynamique d’expressions, ni chargement d’objets exécutables, ni commande lancée par l’interpréteur de commandes depuis des données reçues.

## Réseau et dépendances

L’application n’ouvre aucune connexion réseau. Seule l’installation des bibliothèques en demande une, par pip ; les vérifications `pip-audit` des Actions interrogent un service de vulnérabilités et ne font pas partie de l’application utilisateur.

Les dépendances sont figées dans `requirements.txt`. Examinez les mises à jour proposées avant de les accepter. Le fichier [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) recense leurs licences.
