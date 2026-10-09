# legacy : l'existant, conservé pour référence

## `fiches/`
L'ancien gabarit des fiches d'achat par artiste, réalisées à la main avant ce dépôt (septembre 2026). Il est copié tel quel, n'est pas importé par le code, et ruff ne le vérifie pas. Le nouveau rendu (jalons 2 et 4.1) le réécrira dans `src/mod/pages/`.

| Fichier | Rôle |
|---|---|
| `gen.py` | Générateur : `recap.json` → `recap.html` |
| `_head.html` | En-tête commun : thème clair ou sombre, lecture sur téléphone, en-têtes de tableau fixes, pastilles de qualité |

`tests/test_purchase_sheets.py` vérifie qu'il relit une fiche fictive. Sur la machine de l'auteur, il relit aussi les fiches réelles, qui restent hors dépôt (`[references] purchase_sheets`).

## `dap/`
L'ancienne synchronisation du baladeur et la sauvegarde froide (commandes `disco dap` et `disco sauvegarde`, jalon 0), retirées du programme parce qu'elles ne sont plus d'actualité : elles seront réécrites dans `src/mod/copies/` (issue #54). Le moteur de copie qu'elles utilisaient reste en service (`src/backend/mirror.py`, testé par `tests/backend/test_mirror.py`).

| Fichier | Rôle |
|---|---|
| `dap.py` | Opérations baladeur (synchro, envoyer, récupérer, restaurer) et sauvegarde froide |
| `synchro_discotheque.cmd` | Lanceur posé sur le baladeur |
| `test_dap.py` | Ses anciens tests, qui ne sont plus lancés |

Ces fichiers ne sont ni importés, ni testés, ni vérifiés par ruff.

## Scripts de l'audit
Les scripts de l'audit de septembre 2026 (intégrité, spectre, ReplayGain, doublons, tags par lots) **restent hors dépôt** : ils étaient liés à la machine et à une session de travail précise. Leur emplacement est donné par `[references] audit` dans `config.toml`. Ils servent de référence pour réécrire les algorithmes dans `src/mod/analyse/` et de base de comparaison pour la non-régression (issue de la première passe complète, jalon 1.1).
