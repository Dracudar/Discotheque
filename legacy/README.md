# legacy : l'existant, conservé pour référence

## `fiches/`
L'ancien gabarit des fiches d'achat par artiste, réalisées à la main avant ce dépôt (septembre 2026). Il est copié tel quel, n'est pas importé par le code, et ruff ne le vérifie pas. Le nouveau rendu (jalons 2 et 4.1) le réécrira dans `src/disco/`.

| Fichier | Rôle |
|---|---|
| `gen.py` | Générateur : `recap.json` → `recap.html` |
| `_head.html` | En-tête commun : thème clair ou sombre, lecture sur téléphone, en-têtes de tableau fixes, pastilles de qualité |

`tests/test_fiches_ref.py` vérifie qu'il relit une fiche fictive. Sur la machine de l'auteur, il relit aussi les fiches réelles, qui restent hors dépôt (`[references] fiches_achat`).

## Scripts de l'audit
Les scripts de l'audit de septembre 2026 (intégrité, spectre, ReplayGain, doublons, tags par lots) **restent hors dépôt** : ils étaient liés à la machine et à une session de travail précise. Leur emplacement est donné par `[references] audit` dans `config.toml`. Ils servent de référence pour réécrire les algorithmes dans `src/disco/` et de base de comparaison pour la non-régression (issue de la première passe complète, jalon 1.1).
