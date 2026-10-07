# Documentation

| Document | Contenu |
|---|---|
| `ia-locale.md` | Besoin et matériel pour l'IA locale (cas ambigus uniquement). |
| `sqlite/` | Notes du cours SQLite (mode mentor), créées en phase 1. |

La spécification des fiches d'achat reste **hors dépôt**, parce qu'elle contient des exemples tirés de la discothèque. Elle se trouve à côté des fiches réelles (`[references] fiches_achat`), avec une copie dans le projet Claude de l'auteur.

Le plan complet (décisions, phases, chiffrage, risques) est tenu dans un projet Claude privé. En voici le résumé.

## Jalons

Le suivi se fait dans les jalons et issues GitHub (GitHub Project « Discothèque », vue Roadmap).

Les branches de livrable partent de `develop`, et leurs PR visent `develop`. `main` ne reçoit que les mises en production.

| Jalon | Contenu | Branche |
|---|---|---|
| 0 | Socle : dépôt, configuration, `disco doctor`, CI Windows, import de l'existant | `phase-0/socle` |
| 1.1 | Index SQLite (mode mentor) + moteur d'analyse en un seul décodage | `phase-1.1/…` |
| 1.2 | Lot ReplayGain sur toute la discothèque (lancé par Dracudar) | |
| 2 | Pages album, navigation, recherche globale hors ligne | |
| 3.1 | Catalogue de référence : MusicBrainz, AcoustID, Wikidata | |
| 3.2 | Paroles : existant puis LRCLIB, `.lrc` à côté des pistes (lot validé) | |
| 4.1 | Pages artiste et achats (Qobuz), validation sur les fiches réelles (hors dépôt) | |
| 4.2 | Traductions (IA locale, FR / EN) et romanisation des langues non latines | |
| 5 | Pages projet (franchise → œuvre) et compositeur | |
| 6 | Mises à jour hebdo et à la demande, surveillance de `_sort` | |
| 7 | Serveur local, puis accès distant (lecteur : à cadrer) | |

## Catégories (dossiers de premier niveau)

| Dossier | Type | Pages | ReplayGain album |
|---|---|---|---|
| Artists | artistes | oui | oui |
| Classical music | classique | oui | oui |
| Compilations | compilations | oui | oui |
| Musicals, Soundtrack | projets | oui | oui |
| Bulk | vrac | non | non (piste seulement) |
| `_sort` | arrivées (surveillance) | non | après rangement |
| `_data`, `_bot`, `_log`, `_reports`, `_to_delete` | dossiers système (tout `_…` non déclaré), ignorés | — | — |

Ce sont les catégories par défaut, intégrées au programme : la table fait foi dans `src/disco/modeles/config_defaut.toml`. Les catégories propres à un usage (une copie de `Soundtrack` pour un genre précis, une archive séparée de `Bulk` comme `Night`) s'ajoutent dans `<racine>/_bot/config.toml` ; une catégorie par défaut peut y être redéfinie clé par clé, ou retirée avec `type = "ignore"`.
