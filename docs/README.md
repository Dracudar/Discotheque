# Documentation

| Document | Contenu |
|---|---|
| `ARCHITECTURE.md` | Couches du code, règle de dépendance, circulation par la base, où ranger un nouveau module. |
| `lots.md` | Cycle d'un lot : `_decisions.csv`, `traiter.bat`, `disco lot`, `review`, `reject`, contrat des mods. |
| `ia-locale.md` | Besoin et matériel pour l'IA locale (cas ambigus uniquement). |
| `sqlite/` | Notes du cours SQLite (mode mentor), créées en phase 1. |
| `qt/` | Notes du cours Qt (mode mentor), créées à l’étape 8. |

La spécification des fiches d'achat reste **hors dépôt**, parce qu'elle contient des exemples tirés de la discothèque. Elle se trouve à côté des fiches réelles (`[references] purchase_sheets`), avec une copie dans le projet Claude de l'auteur.

Le plan complet (décisions, phases, chiffrage, risques) est tenu dans un projet Claude privé. En voici le résumé.

## Étapes (jalons)

Le suivi se fait dans les jalons et issues GitHub (GitHub Project « Discothèque »). Les traitements passent avant l'interface : ce qui fait vivre la discothèque au quotidien (pistes analysées, propres, rangées, copiées) vient d'abord. Pas de dates fixes.

Les branches de livrable partent de `develop`, et leurs PR visent `develop`. `main` ne reçoit que les versions : `v0.1.0` à la fin de l'étape 3, puis une par étape ; `v1.0.0` sera la première vraie mise en production.

| Jalon | Contenu |
|---|---|
| Audit et tri | Travail préalable sur la discothèque (audit de septembre 2026, bascule, années et dossiers « année - album ») |
| 0. Socle | Dépôt, configuration, `disco doctor`, CI, architecture, langue du code |
| 1. Base SQLite | Schéma, migrations, accès concurrents (mode mentor) |
| 2. Analyses | Scan, moteur en un seul décodage et mesures, exécution en arrière-plan, version compilée et installateur, lot ReplayGain |
| 3. Tri et vérification des pistes | Vérification des conventions, lots de correction ; **`v0.1.0`** |
| 4. Surveillance des données | Changements de la discothèque, arrivées de `_sort` et rangement, purge automatique de la corbeille (si activée) |
| 5. Copies et archivage | Partie commune, copie vers le baladeur, archivage, puis copie complète unique |
| 6. Catalogue, paroles et traductions | MusicBrainz, AcoustID, Wikidata, pages à la demande, franchises et œuvres, paroles, traductions (en arrière-plan) |
| 7. Sorties et achats | Nouvelles sorties, Qobuz et livrables d'achat, favoris, passes régulières, mise à jour du programme |
| 8. Interface Qt | Navigation, recherche, pages, écrans de gestion, configurateur |
| 9. Serveur et web | Serveur, interface web, accès distant jamais public |
| Projets secondaires | Sans ordre : déplacement de la discothèque, automatisation du Project… |

## Catégories (dossiers de premier niveau)

| Dossier | Type | Pages | ReplayGain album |
|---|---|---|---|
| Artists | artists | oui | oui |
| Classical music | classical | oui | oui |
| Compilations | compilations | oui | oui |
| Musicals, Soundtrack | projects | oui | oui |
| Bulk | bulk | non | non (piste seulement) |
| `_sort` | arrivées (surveillance) | non | après rangement |
| `_bot`, `_data`, `_workspace`, `_playlists` | dossiers système (tout `_…` non déclaré), ignorés | — | — |

Ce sont les catégories par défaut, intégrées au programme : la table fait foi dans `src/assets/config_default.toml`. Les catégories propres à un usage (une copie de `Soundtrack` pour un genre précis, une archive séparée de `Bulk` comme `Night`) s'ajoutent dans `<racine>/_bot/config.toml` ; une catégorie par défaut peut y être redéfinie clé par clé, ou retirée avec `type = "ignore"`.

## Dossiers système (racine)

```
<racine>
├─ _sort           arrivées : boîte de dépôt de l'opérateur
├─ _playlists      playlists du baladeur
├─ _bot            installation de production, config, outils
│  └─ _log         journal de toutes les actions du bot (dont celui de la corbeille)
├─ _data           données générées (régénérables), sauf la base
│  ├─ _base        index SQLite, jamais effacé
│  └─ _cache       réponses des services en ligne
└─ _workspace      tout le travail du bot, sur des copies
   ├─ _process     copies en cours de traitement, jetables
   ├─ _in_review   résultats tranchés par le bot, en attente de validation (lot)
   ├─ _pending     cas que le bot ne sait pas trancher
   ├─ _reports     rapports lisibles du travail effectué
   └─ _bin         corbeille (purge facultative : trash.retention_days)
```

Le bot ne travaille jamais sur les fichiers bruts. Un fichier suit le cycle `_sort` → `_process` → `_in_review` (décision à valider) ou `_pending` (pas encore de décision) → lot validé : le résultat entre dans la discothèque, ce qu'il remplace part dans `_bin`. Chaque dossier a sa clé dans `[paths]` (voir `configuration.md`) ; les sous-dossiers de `_workspace` suivent `paths.workspace`.
