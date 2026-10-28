# Modèle de données

Ce document décrit **ce que la base doit représenter** : les entités, leurs identifiants, les tables, leurs champs et leurs liaisons, et la correspondance avec les tags des fichiers. C'est le point de départ du schéma SQLite (#32), qui s'écrira **en mode mentor** : ce document ne contient pas de SQL, les types, contraintes et index se décident pendant l'écriture du schéma.

État : **proposition v0 du 2026.10.28**, issue des discussions de #114. Les points encore ouverts sont listés à la fin. Tous les exemples sont inventés.

## 1. Principes

1. **Un nom n'est pas une clé.** Homonymes, alias, graphies et collaborations rendent les noms ambigus. Les tables se relient uniquement par des identifiants.
2. **Deux identifiants par entité, plus le MBID :**
   - un **entier** (`id`, clé primaire), pour tous les liens **dans** la base ; il n'en sort jamais ;
   - un **identifiant public permanent** (`public_id`, unique), pour tout ce qui est **hors** de la base : tags, adresses des pages, surcharges, journaux, rapports. Il ne change jamais ;
   - le **MBID** (`mbid`), facultatif, unique quand il est renseigné. Ce n'est pas une clé : poser, corriger ou retirer un MBID ne touche qu'une case. Un MBID peut lui-même changer (fusion de deux fiches sur MusicBrainz).
3. **Une case, une valeur.** Pas de liste dans un champ (« A-xxx, A-yyy ») : une liste devient une table de liaison, avec une ligne par élément.
4. **Un identifiant ne porte aucune information qui pourrait se révéler fausse** : seulement le type de l'entité. Les parentés (original, variante, œuvre) sont dans des tables, corrigeables.
5. **Corriger, c'est fusionner, jamais renuméroter.** Deux fiches qui désignent la même chose sont fusionnées **après validation** : l'une est conservée, l'autre devient une redirection (`redirect`). Une fusion peut s'annuler.
6. **La base ne suit pas l'arborescence des dossiers.** Artiste > album > piste n'est qu'une présentation. Chaque entité a sa table.
7. **Posséder un morceau, c'est avoir un fichier.** Les enregistrements, éditions et œuvres existent aussi sans fichier (discographies, éditions non possédées pour les achats, originaux des reprises et des remix).
8. **Chaque donnée garde son origine et son état** (MusicBrainz, boutique, année de mise en ligne, saisie manuelle ; validé ou à vérifier), pour qu'une passe automatique n'écrase jamais une décision manuelle.

## 2. Identifiants publics

Format : **une lettre de type, un tiret, une partie aléatoire**, par exemple `A-7K3QX9M2TA` (10 caractères en base 32 de Crockford, sans I, L, O, U ; environ 50 bits). Pas de compteur : la sandbox et la production n'ont pas à se coordonner. En cas de collision (improbable), nouveau tirage. Format exact à confirmer avec le schéma.

| Lettre | Entité | Table |
|---|---|---|
| **A** | artiste : personne, groupe, orchestre, compositeur | `artist` |
| **R** | album (groupe de sorties) | `album` |
| **T** | enregistrement : une interprétation, un mixage | `recording` |
| **W** | œuvre : la chanson ou la composition en tant qu'écrite | `work` |
| **P** | projet : jeu, film, série, extension, événement, franchise, spectacle | `project` |
| **L** | label, éditeur | `label` |
| **S** | studio : développement de jeux, production de films | `studio` |

Éditions, lignes de tracklist et fichiers n'ont que l'entier interne (identifiant public à ajouter si un besoin apparaît).

## 3. Vue d'ensemble

```
A artiste ──┬── album_credit ──────► R album ◄───────── project_album ────────┐
            │                        │                                        │
            │                        ▼                                        │
            │                     édition ◄── publie ── L label               │
            │                        │                                        │
            │                        ▼                                        ├── P projet ◄─ parent
            │                      piste ◄┄┄┄┄┄┄┄┄ fichier (mesures)          │   (franchise → jeu → événement)
            │                        │               │                        │   ◄── project_studio ── S studio
            │                        ▼               ▼                        │
            ├── recording_credit ──► T enregistrement ◄── recording_project ──┤
            │                        │  ▲                                     │
            │                        │  └── recording_relation                │
            │                        │      (remix, mashup, remaster…)        │
            │                        ▼                                        │
            └── work_credit ───────► W œuvre ◄──────────────── work_project ──┘
                                     │  ▲
                                     │  └── work_relation (parodie, traduction…)
                                     ▼
                                  paroles (synchronisées par T)
```

Lecture : chaque table de liaison est nommée sur sa flèche ; `┄` marque un lien facultatif. L'artiste (A) apparaît une fois, avec ses trois sortes de crédits : sur l'album, sur l'enregistrement (interprètes, invités, remixeurs) et sur l'œuvre (compositeurs, auteurs). Le projet (P) se relie aux albums, aux enregistrements et aux œuvres ; le label (L) publie les éditions ; le studio (S) est rattaché au projet.

- Chaque **enregistrement** a **une œuvre** (créée automatiquement, en un pour un, pour une chanson ordinaire).
- Une **œuvre** renvoie vers sa **première interprétation**, avec ou sans fichier.
- Un **fichier** pointe vers un enregistrement ; la ligne de tracklist est facultative (fichiers en vrac des catégories `bulk`).
- Les **mesures** (intégrité, ReplayGain, spectre…) appartiennent au **fichier** : un même enregistrement peut exister en FLAC et en MP3, ou dans un autre master.

### Liaisons, table par table

Lecture : « un album → plusieurs éditions » se lit « un album a plusieurs éditions, une édition appartient à un seul album ». Une table de liaison (plusieurs à plusieurs) porte en plus un rôle et un ordre.

**Artistes**

| Liaison | Relie | Sens |
|---|---|---|
| `artist_alias` | artiste → noms | un artiste, plusieurs noms |
| `artist_relation` | artiste ↔ artiste | membre de, sous-groupe, projet solo |
| `artist_link` | artiste → profils | un artiste, plusieurs profils |
| `artist_flag` | artiste → marquages | un artiste, plusieurs marquages |

**Sorties**

| Liaison | Relie | Sens |
|---|---|---|
| `edition.album_id` | album → éditions | un album, plusieurs éditions |
| `edition.label_id` | label → éditions | un label, plusieurs éditions ; une édition, un label au plus |
| `track.edition_id` | édition → pistes | une édition, plusieurs pistes (la tracklist) |
| `track.recording_id` | enregistrement → pistes | un enregistrement, plusieurs pistes (album, compilation…) |
| `album_credit` | album ↔ artistes | plusieurs à plusieurs, avec nom crédité, rôle, ordre |
| `album_type` | album → types | un album, plusieurs types secondaires |
| `edition_marker` | édition → marqueurs | `RELEASETYPE` |

**Enregistrements et œuvres**

| Liaison | Relie | Sens |
|---|---|---|
| `recording.work_id` | œuvre → enregistrements | une œuvre, plusieurs interprétations ; chaque enregistrement a **une** œuvre |
| `work.first_recording_id` | œuvre → enregistrement | la première interprétation (une au plus) |
| `recording_credit` | enregistrement ↔ artistes | interprètes, invités, remixeurs |
| `recording_relation` | enregistrement ↔ enregistrement | dérivé → sources (remix, mashup : plusieurs sources) |
| `recording_marker` | enregistrement → marqueurs | `TRACKTYPE` |
| `work_credit` | œuvre ↔ artistes | compositeurs, auteurs, arrangeurs |
| `work_relation` | œuvre ↔ œuvre | parodie, traduction, arrangement → œuvre de base |

**Projets et studios**

| Liaison | Relie | Sens |
|---|---|---|
| `project.parent_id` | projet → sous-projets | franchise → jeu → extension ou événement |
| `project_album` | projet ↔ albums | bande originale, extension, version d'une boutique |
| `project_studio` | projet ↔ studios | développement, édition, production |
| `work_project` | œuvre ↔ projets | thème, générique, chanson d'un événement |
| `recording_project` | enregistrement ↔ projets | morceau lié au projet sans album de bande originale |

**Paroles**

| Liaison | Relie | Sens |
|---|---|---|
| `lyrics_text.work_id` | œuvre → textes | une œuvre, plusieurs textes (original, romanisation, traductions) |
| `lyrics_text.recording_id` | enregistrement → texte propre | facultatif (live improvisé) |
| `lyrics_text.derived_from_id` | texte → textes dérivés | traduction ou romanisation d'un texte |
| `lyrics_sync` | enregistrement ↔ textes | horodatages d'un enregistrement pour un texte |

**Fichiers**

| Liaison | Relie | Sens |
|---|---|---|
| `file.recording_id` | enregistrement → fichiers | plusieurs fichiers possibles (formats, éditions) |
| `file.track_id` | piste → fichiers | **facultatif** ; deux fichiers sur la même piste = doublon |
| `file_tag` | fichier → tags bruts | une ligne par valeur |
| `measurement` | fichier → mesures | une ligne par mesure et par version |

## 4. Tables

Les champs listés sont le contenu attendu, pas le schéma définitif. `source` et `state` (origine et état de la donnée, principe 8) sont notés là où ils sont indispensables.

### 4.1 Artistes

**`artist`** : un artiste, un groupe, un orchestre, un compositeur.

| Champ | Contenu |
|---|---|
| `id`, `public_id` (A-), `mbid` | identifiants |
| `name`, `sort_name` | nom affiché, nom de tri |
| `kind` | personne, groupe, orchestre, chœur, autre |
| `disambiguation` | mention qui distingue les homonymes (reprise de MusicBrainz ou saisie) |
| `country`, `begin_year`, `end_year` | renseignements généraux (Wikidata, MusicBrainz) |
| `follow_level` | niveau de suivi des sorties : 0 (présent seulement en invité, exclu par défaut, activable), normal, suivi, favori, exclu (#72). Donnée utilisateur |

**`artist_alias`** : les autres noms d'un artiste.

| Champ | Contenu |
|---|---|
| `artist_id` | l'artiste |
| `name`, `normalized_name` | le nom ; sa forme normalisée pour la recherche |
| `kind` | nom de dossier, forme latine, forme d'origine (`Nom latin (日本語)`), ancien nom, graphie officielle, nom sur une plateforme |
| `language` | langue ou écriture (code BCP 47) |

**`artist_relation`** : membre de, sous-groupe de, projet solo de… (`artist_id`, `related_artist_id`, `kind`, années).

**`artist_link`** : profils et fiches ailleurs (`artist_id`, `kind` : MusicBrainz, Wikidata, Discogs, Qobuz, SoundCloud, Bandcamp, YouTube, site officiel ; `url`, `source`, `state`). Un lien vers un profil se pose une fois, depuis MusicBrainz ou à la main, puis il est conservé (#115).

**`artist_flag`** : marquages (reprises, homonymes à surveiller…), une ligne par marquage.

### 4.2 Labels, studios, projets

**`label`** : `id`, `public_id` (L-), `mbid`, `name`.

**`studio`** : `id`, `public_id` (S-), `name`, `kind` (développement de jeux, production de films…).

**`project`** : ce que regroupent les pages projet.

| Champ | Contenu |
|---|---|
| `id`, `public_id` (P-) | identifiants |
| `name`, `kind` | nom ; film, série, jeu, extension (DLC), événement, chapitre, franchise, spectacle (comédie musicale) |
| `parent_id` | projet parent : franchise → jeu → extension ou événement |
| `year` | année de sortie |
| `follow_level` | comme pour les artistes |

**`project_studio`** : `project_id`, `studio_id`, `role` (développement, édition, production). **Le studio est rattaché au projet, pas à l'album** : pour une bande originale, l'artiste de l'album (`ALBUMARTIST`) se déduit du studio du projet (développement pour un jeu, production pour un film ou une série). Un sous-projet (extension, événement) hérite des studios de son parent, sauf s'il a les siens. Un cas qui ne rentre pas (album lié à plusieurs projets de studios différents) passe par une surcharge.

**`project_album`** : `project_id`, `album_id`, `role` (bande originale, extension, version d'une boutique, enregistrement de la troupe…).

### 4.3 Albums et éditions

**`album`** : le groupe de sorties, l'album « en général », celui des fiches d'achat.

| Champ | Contenu |
|---|---|
| `id`, `public_id` (R-), `mbid` | identifiants (MBID du groupe de sorties) |
| `title` | titre |
| `primary_type` | album, EP, single, autre |
| `first_release_date` | date de la première sortie |

**`album_type`** : types secondaires, plusieurs par album (compilation, bande originale, live, remix…), une ligne par type.

**`album_credit`** : artistes de l'album (`album_id`, `artist_id`, `credited_name`, `role`, `position`, `join_phrase`). `credited_name` garde le nom tel qu'il est crédité sur la sortie ; `join_phrase` (« & », « feat. », « × ») permet de recomposer le crédit affiché.

**`edition`** : la sortie précise. Un dossier de la discothèque correspond à une édition.

| Champ | Contenu |
|---|---|
| `id`, `album_id`, `mbid` | identifiants (MBID de la sortie) ; album auquel elle appartient |
| `title` | titre s'il diffère de l'album |
| `release_date` | `RELEASEDATE` |
| `country`, `label_id`, `catalog_number`, `barcode` | renseignements de la sortie |
| `store` | boutique d'origine quand le contenu en dépend (plateforme de jeu, magasin de musique) |
| `media_count` | nombre de disques |
| `source`, `state` | origine de l'identification (MusicBrainz, boutique, année de mise en ligne, saisie) et état |

**`edition_marker`** : `RELEASETYPE`, plusieurs valeurs (live, remix…), seulement si toutes les pistes portent le marqueur.

**`track`** : une ligne de tracklist.

| Champ | Contenu |
|---|---|
| `id`, `edition_id`, `recording_id` | la ligne, son édition, son enregistrement |
| `disc_number`, `position` | place dans l'édition (unique par édition) |
| `title_on_release`, `length_ms` | titre et durée tels qu'ils figurent sur cette édition, s'ils diffèrent |

### 4.4 Enregistrements et œuvres

**`recording`** : une interprétation, un mixage.

| Champ | Contenu |
|---|---|
| `id`, `public_id` (T-), `mbid`, `isrc` | identifiants |
| `work_id` | l'œuvre interprétée (**obligatoire**) |
| `title`, `version` | titre ; précision qui ne va pas dans le titre (`VERSION`) |
| `date` | année de la version (`DATE`) |
| `length_ms` | durée de référence |
| `explicit` | paroles explicites (information, pas un marqueur) |
| `source`, `state` | origine et état |

**`recording_credit`** : artistes qu'on entend (`recording_id`, `artist_id`, `credited_name`, `role` : principal, invité, remixeur ; `position`, `join_phrase`).

**`recording_marker`** : `TRACKTYPE`, plusieurs valeurs (cover, remix, live, parody, clean…). La liste vient de la configuration (#82). Le type est renseigné même quand le titre ne porte pas de marqueur (dérivé qui a son propre titre).

**`recording_relation`** : un enregistrement dérivé d'un autre.

| Champ | Contenu |
|---|---|
| `recording_id`, `source_recording_id` | le dérivé, sa source |
| `kind` | remix, mashup, remaster, edit, version clip, nightcore, sped up, slowed, reprise qui garde l'instrumental d'origine… |
| `position` | ordre des sources (mashup) |

**`recording_project`** : enregistrement lié à un projet sans être sur un album de bande originale (`role` : thème, générique, chanson d'un événement).

**`work`** : l'œuvre.

| Champ | Contenu |
|---|---|
| `id`, `public_id` (W-), `mbid` | identifiants |
| `title`, `language` | titre ; langue des paroles |
| `first_recording_id` | première interprétation (avec ou sans fichier) ; vide pour une œuvre traditionnelle ou du domaine public sans enregistrement d'origine |

**`work_credit`** : compositeurs, auteurs, arrangeurs (`work_id`, `artist_id`, `role`, `position`). « Traditionnel » est un artiste spécial.

**`work_relation`** : œuvre basée sur une autre (`work_id`, `base_work_id`, `kind` : parodie, traduction, arrangement). Une parodie avec de nouvelles paroles est une **nouvelle œuvre**.

**`work_project`** : œuvre issue d'un projet (`role` : thème, chanson, générique).

### 4.5 Paroles

**`lyrics_text`** : tous les textes, une ligne par texte et par langue.

| Champ | Contenu |
|---|---|
| `id`, `work_id` | le texte, son œuvre |
| `recording_id` | facultatif : texte propre à un enregistrement (live improvisé) qui prend le pas sur celui de l'œuvre |
| `language` | code BCP 47 : `ja` (original), `ja-Latn` (romanisation), `fr`, `en` (traductions) |
| `kind` | original, romanisation, traduction |
| `derived_from_id` | texte d'où il dérive (traduction, romanisation) |
| `text` | le texte, découpé en lignes comme l'original |
| `source`, `model`, `model_version` | LRCLIB, saisie, IA locale ; modèle et version pour l'IA |

**`lyrics_sync`** : horodatages d'**un enregistrement** pour un texte (`recording_id`, `lyrics_text_id`, contenu LRC). Les traductions et la romanisation gardent le découpage en lignes de l'original et se calent sur sa synchronisation.

La configuration ne dit que les langues à **générer** : on n'ajoute jamais de table ni de colonne par langue.

### 4.6 Fichiers et mesures

**`file`** : un fichier de la discothèque.

| Champ | Contenu |
|---|---|
| `id` | identifiant |
| `path` | chemin relatif à la racine, séparateur `/` (#32) |
| `category` | catégorie de premier niveau (déclarée dans la configuration) |
| `recording_id` | enregistrement contenu (vide tant qu'il n'est pas identifié) |
| `track_id` | ligne de tracklist, **facultative** |
| `size`, `mtime`, `audio_hash` | repérage des changements, empreinte audio (#98) |
| `codec`, `sample_rate`, `bit_depth`, `channels`, `duration_ms` | format |
| `source`, `source_origin`, `source_url` | source du fichier (#102) |
| `state` | présent, absent, à la corbeille |

**`file_tag`** : copie brute des tags (`file_id`, `key`, `value`, `position`), une ligne par valeur. C'est une copie, pour comparer et surveiller, pas un lien.

**`measurement`** : une ligne par mesure, par fichier et par version d'algorithme (#33).

Plusieurs fichiers sur **la même ligne de tracklist** sont un **doublon** (signalé). Le même enregistrement sur plusieurs éditions (album et compilation) est normal : une ligne de tracklist et un fichier par édition.

### 4.7 Fusions et données de travail

**`redirect`** : `entity_kind`, `old_public_id`, `new_public_id`, date, lot. Une page, une surcharge ou un tag qui cite l'ancien identifiant est redirigé.

Les tables de travail (lots, actions et décisions, renommages, corbeille, file de demandes, signalements, liste d'achats) sont décrites dans les commentaires de #32 et ne sont pas reprises ici.

## 5. Correspondance avec les tags

Les tags d'un fichier sont **déduits de la base** et écrits par lots validés. Conventions détaillées dans #82.

| Tag | Source dans la base |
|---|---|
| `TITLE` | `recording.title` et marqueurs, au format de #82 |
| `ARTIST` (plusieurs valeurs) | `recording_credit` : noms crédités |
| `ALBUMARTIST` | `album_credit` ; pour une bande originale, studio du projet (`project_album` → `project_studio`) |
| `ALBUM` | `album.title` (ou `edition.title`) |
| `TRACKNUMBER`, `DISCNUMBER` | `track` |
| `DATE` | `recording.date` |
| `RELEASEDATE` | `edition.release_date` |
| `TRACKTYPE` | `recording_marker` |
| `RELEASETYPE` | `edition_marker` |
| `VERSION` | `recording.version` |
| `REMIXER` | `recording_credit` de rôle remixeur |
| `ORIGINALTRACK` (plusieurs valeurs) | reprise : première interprétation de l'œuvre ; remix, mashup : `recording_relation`. Une valeur par origine : `Artiste - Année - Titre` (année sur 4 chiffres, `????` si inconnue) |
| `LABEL` | `edition.label_id` |
| `SOURCEURL` | `file.source_url` |
| `MUSICBRAINZ_ARTISTID`, `MUSICBRAINZ_ALBUMARTISTID` | `artist.mbid` des crédits |
| `MUSICBRAINZ_RELEASEGROUPID`, `MUSICBRAINZ_ALBUMID`, `MUSICBRAINZ_TRACKID` | `album.mbid`, `edition.mbid`, `recording.mbid` |

`ORIGINALTRACK` remplace `ORIGINALARTIST`, `ORIGINALTRACKYEAR` et `ORIGINALTITLE` : trois tags parallèles rendaient ambigu un original en duo face à un mashup de deux originaux.

## 6. Passes automatiques

- **Vérification des identifiants** (passe complète mensuelle, tous les artistes, niveau 0 compris) : nouveau MBID proposé avec un niveau de confiance (plusieurs albums concordants, jamais le seul nom) ; MBID fusionné chez MusicBrainz signalé ; doublons signalés. **Tout passe par une validation** ; une fusion se valide au cas par cas.
- **Nouvelles sorties** : fréquence selon le niveau de suivi, réglable dans la configuration (#28).

## 7. Questions ouvertes

- [ ] Format exact de l'identifiant public (longueur, alphabet) et tags où l'écrire dans les fichiers, pour survivre à une reconstruction de la base.
- [ ] Identifiant public pour les éditions, si les pages ou les surcharges en ont besoin.
- [ ] Forme de `source` et `state` : colonnes sur chaque table, ou table de surcharges commune.
- [ ] Synchronisation : contenu LRC brut ou une ligne par vers.
- [ ] Signe des marqueurs dans les titres, quand un nom de sortie contient lui-même des crochets (#82).
