# Configuration

Le programme fonctionne **sans aucun fichier de configuration** : la structure de la racine et les catégories standard sont intégrées. Un `config.toml` ne sert qu'à écrire ce qui diffère du défaut.

## Les trois couches

La configuration se superpose en trois couches. Pour chaque clé, la couche la plus haute l'emporte.

| Couche | Fichier | Contient | Obligatoire |
|---|---|---|---|
| 1. `défaut` | `src/assets/config_defaut.toml` (intégré au programme) | réglages d'analyse, catégories standard | — |
| 2. `_bot` | `<racine>\_bot\config.toml` | réglages personnels : baladeur, sauvegarde, références, catégories en plus | non |
| 3. `clone` | `config.toml` du clone de développement | `racine` (la sandbox), et toute surcharge | non (en développement : `racine`) |

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

1. La clé `[chemins] racine`, si elle est écrite (cas du clone de développement).
2. Sinon, le dossier parent de `_bot` :
   - si la config est rangée dans `<racine>\_bot\config.toml` ;
   - ou, sans aucun fichier, si le programme tourne depuis `<racine>\_bot` (version compilée ou environnement `.venv`).
3. Sinon, le programme s'arrête : « Racine introuvable ».

## Production et développement

**Production.** Rien n'est obligatoire. `<racine>\_bot\config.toml` ne contient que les réglages personnels, sans `racine` (elle se déduit) :

```toml
[dap]
destination = 'X:\Baladeur\Music'

[sauvegarde]
destination = 'X:\Sauvegarde\Musique'
```

**Développement.** Le `config.toml` du clone (jamais versionné) donne seulement la racine de la sandbox. Le reste vient du défaut, puis du `_bot\config.toml` de la sandbox :

```toml
[chemins]
racine = 'X:\Sandbox\Musique'
```

Les chaînes entre apostrophes sont littérales : les `\` de Windows n'ont pas à être doublés.

## Catégories

Une catégorie est un dossier de premier niveau de la racine.

| Clé | Rôle |
|---|---|
| `type` | `artistes`, `classique`, `compilations`, `projets`, `vrac`, `arrivees`, `ignore` |
| `pages` | génère des pages (album, artiste, projet, compositeur) |
| `rg_album` | calcule et écrit le ReplayGain album (sinon piste seulement) |

### Catégories par défaut

| Dossier | Type | Pages | ReplayGain album |
|---|---|---|---|
| Artists | artistes | oui | oui |
| Classical music | classique | oui | oui |
| Compilations | compilations | oui | oui |
| Musicals | projets | oui | oui |
| Soundtrack | projets | oui | oui |
| Bulk | vrac | non | non |
| `_sort` | arrivees | non | non |

Les autres dossiers qui commencent par `_` (`_data`, `_bot`, `_log`…) sont ignorés automatiquement. `disco doctor` signale tout autre dossier de la racine qui n'est déclaré nulle part.

### Ajouter, modifier ou retirer une catégorie

Ces réglages se font dans `<racine>\_bot\config.toml`.

**Ajouter** une catégorie : la déclarer en entier.

```toml
[categories."Ma Catégorie"]
type = "projets"
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

- **Tables** (`[chemins]`, `[categories."…"]`…) : fusionnées clé par clé.
- **Valeurs simples** (texte, nombre, booléen) : la couche du dessus remplace celle du dessous.
- **Listes** : remplacées **en bloc**, jamais fusionnées. Pour ajouter un élément à une liste du défaut, il faut réécrire la liste complète.

## Lire la configuration chargée

`disco config` affiche chaque valeur avec son origine entre crochets :

```
Fichiers  : X:\Musique\_bot\config.toml + X:\Projets\Discotheque\config.toml
Racine    : X:\Musique  [clone]
Sortie    : X:\Musique\_data  [déduit]
Sauvegarde: X:\Sauvegarde\Musique  [_bot]
Référence : -18.0 LUFS  [défaut]
Catégories :
  Artists                    artistes     pages=oui RG album=oui  [défaut]
  Ma Catégorie               projets      pages=oui RG album=oui  [_bot]
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

Voir [`config.example.toml`](../config.example.toml), commenté, et [`config_defaut.toml`](../src/assets/config_defaut.toml) pour les valeurs par défaut.
