# Configuration

Le programme fonctionne **sans aucun fichier de configuration** : la structure de la racine et les catégories standard sont intégrées. Un `config.toml` ne sert qu'à écrire ce qui diffère du défaut.

## Les trois couches

La configuration se superpose en trois couches. Pour chaque clé, la couche la plus haute l'emporte.

| Couche | Fichier | Contient | Obligatoire |
|---|---|---|---|
| 1. `défaut` | `src/assets/config_default.toml` (intégré au programme) | réglages d'analyse, catégories standard | — |
| 2. `_bot` | `<racine>\_bot\config.toml` | réglages personnels : catégories en plus, outils | non |
| 3. `clone` | `config.toml` du clone de développement | `root` (la sandbox), références hors dépôt, et toute surcharge | non (en développement : `root`) |

Les chemins des dossiers système (`_data`, `_log`…) et des outils ne sont écrits nulle part par défaut : ils se **déduisent** de la racine.

### Où le programme cherche le fichier

Dans l'ordre :

1. l'option `--config <fichier>` ;
2. la variable d'environnement `DISCO_CONFIG` ;
3. `config.toml` à côté du programme (`_bot` en production, le clone en développement) ;
4. `config.toml` dans le dossier courant.

Un fichier demandé avec `--config` ou `DISCO_CONFIG` doit exister. Sinon, le programme s'arrête sur une erreur, car c'est sans doute une faute de frappe. Pour les emplacements 3 et 4, l'absence de fichier n'est pas une erreur : la configuration par défaut s'applique.

Si le fichier trouvé n'est pas celui de `_bot`, le programme lit **aussi** `<racine>\_bot\config.toml` en dessous (couche 2).

### Comment la racine est trouvée

1. La clé `[paths] root`, si elle est écrite (cas du clone de développement).
2. Sinon, le dossier parent de `_bot` :
   - si la config est rangée dans `<racine>\_bot\config.toml` ;
   - ou, sans aucun fichier, si le programme tourne depuis `<racine>\_bot` (version compilée ou environnement `.venv`).
3. Sinon, le programme s'arrête : « Racine introuvable ».

## Production et développement

Deux modèles sont fournis :

| Modèle | Copier vers | Contenu |
|---|---|---|
| [`src/assets/config.example.toml`](../src/assets/config.example.toml), livré avec le programme | `<racine>\_bot\config.toml` | **tout commenté** : utilisable tel quel (il ne change rien), on décommente seulement ce qui diffère |
| [`config.dev_example.toml`](../config.dev_example.toml), à la racine du dépôt | `config.toml` du clone | `root` (la sandbox) et `[references]` |

**Production.** Rien n'est obligatoire. `<racine>\_bot\config.toml` ne contient que les réglages personnels, sans `root` (elle se déduit), par exemple une catégorie en plus :

```toml
[categories."Archive Exemple"]
type = "bulk"
pages = false
rg_album = false
```

**Développement.** Le `config.toml` du clone (jamais versionné) donne la racine de la sandbox et les données de référence hors dépôt. Le reste vient du défaut, puis du `_bot\config.toml` de la sandbox :

```toml
[paths]
root = 'X:\Sandbox\Musique'

[references]
audit = 'X:\Travail\_audit'
purchase_sheets = 'X:\Travail\Fiches artistes'
```

Les chaînes entre apostrophes sont littérales : les `\` de Windows n'ont pas à être doublés.

## Catégories

Une catégorie est un dossier de premier niveau de la racine.

| Clé | Rôle |
|---|---|
| `type` | `artists`, `classical`, `compilations`, `projects`, `bulk`, `incoming`, `ignore` |
| `pages` | génère des pages (album, artiste, projet, compositeur) |
| `rg_album` | calcule et écrit le ReplayGain album (sinon piste seulement) |

### Catégories par défaut

| Dossier | Type | Pages | ReplayGain album |
|---|---|---|---|
| Artists | artists | oui | oui |
| Classical music | classical | oui | oui |
| Compilations | compilations | oui | oui |
| Musicals | projects | oui | oui |
| Soundtrack | projects | oui | oui |
| Bulk | bulk | non | non |
| `_sort` | incoming | non | non |

Les autres dossiers qui commencent par `_` (`_data`, `_bot`, `_log`…) sont ignorés automatiquement. `disco doctor` signale tout autre dossier de la racine qui n'est déclaré nulle part.

### Ajouter, modifier ou retirer une catégorie

Ces réglages se font dans `<racine>\_bot\config.toml`.

**Ajouter** une catégorie : la déclarer en entier.

```toml
[categories."Ma Catégorie"]
type = "projects"
pages = true
rg_album = true
```

**Modifier** une catégorie par défaut : écrire seulement la clé qui change. Les autres clés gardent leur valeur par défaut.

```toml
[categories."Compilations"]
rg_album = false        # type et pages restent ceux du défaut
```

**Retirer** une catégorie par défaut : la déclarer ignorée. `pages` et `rg_album` passent alors à `false`, quelle que soit leur valeur héritée.

```toml
[categories."Musicals"]
type = "ignore"
```

## Règles de fusion

- **Tables** (`[paths]`, `[categories."…"]`…) : fusionnées clé par clé.
- **Valeurs simples** (texte, nombre, booléen) : la couche du dessus remplace celle du dessous.
- **Listes** : remplacées **en bloc**, jamais fusionnées. Pour ajouter un élément à une liste du défaut, il faut réécrire la liste complète.

## Anciens noms

Jusqu'à la version 0.1, la configuration était en français. Un ancien nom n'est pas ignoré en silence : le programme s'arrête et donne le nouveau nom.

| Ancien | Nouveau |
|---|---|
| `[chemins] racine, sortie, base, cache, journaux, rapports, corbeille, bot, arrivees` | `[paths] root, output, db, cache, logs, reports, trash, bot, incoming` |
| `[outils]` | `[tools]` |
| `[analyse] reference_lufs, surechantillonnage_crete, processus` | `[analysis] reference_lufs, true_peak_oversampling, workers` |
| `[references] fiches_achat` | `[references] purchase_sheets` |
| types `artistes, classique, projets, vrac, arrivees` | `artists, classical, projects, bulk, incoming` |
| `[dap]`, `[sauvegarde]` | retirées : les copies sont refaites dans l'issue #54 |

## Lire la configuration chargée

`disco config` affiche chaque valeur avec son origine entre crochets :

```
Fichiers  : X:\Musique\_bot\config.toml + X:\Projets\Discotheque\config.toml
Racine    : X:\Musique  [clone]
Sortie    : X:\Musique\_data  [déduit]
Fiches    : X:\Travail\Fiches artistes  [clone]
Référence : -18.0 LUFS  [défaut]
Catégories :
  Artists                    artists      pages=oui RG album=oui  [défaut]
  Ma Catégorie               projects     pages=oui RG album=oui  [_bot]
```

| Origine | Signification |
|---|---|
| `défaut` | configuration intégrée au programme |
| `_bot` | `<racine>\_bot\config.toml` |
| `clone` | le `config.toml` trouvé ailleurs (clone de développement, `--config`) |
| `déduit` | calculé : chemin déduit de la racine, outil trouvé dans `_bot\tools` ou le PATH |

Pour une catégorie, l'origine est celle de la couche la plus haute qui la touche.

`disco doctor` liste aussi, sur sa ligne « Configuration », tous les fichiers lus, ou « configuration par défaut » s'il n'y en a aucun.

## Toutes les clés

Voir [`config.example.toml`](../src/assets/config.example.toml), commenté, et [`config_default.toml`](../src/assets/config_default.toml) pour les valeurs par défaut.
