# Architecture du code

Le code est rangé en **couches**, sur le modèle de Morphoz_SnackApp (branche `Refactor`), pour que les deux projets suivent la même convention.

- **`src/` est lui-même le paquet** : pas de sous-dossier au nom du projet. Les imports s'écrivent `from src.backend.config import charger`. La commande installée reste `disco` (`python -m src` en est l'équivalent).
- **Une seule distribution, un seul dépôt** : les dossiers rangent le code, ils ne sont pas publiés séparément.
- **Noms des couches en anglais** (`core`, `backend`, `UI`, `mod`), comme dans SnackApp. Les dossiers métier et le code restent en français, sans accents dans les identifiants.

## Les couches

```
src/
├── __init__.py, __main__.py   « python -m src »
├── __versions__.py    lecteur de assets/versions.toml (versions de la livraison)
├── core/              entrée et environnement
│   ├── cli.py         commandes, envoi vers les mod
│   └── doctor.py      diagnostic de l'environnement
├── backend/           services communs, aucun métier
│   ├── config.py      couches de configuration
│   ├── journal.py     _log et _reports
│   ├── copie.py       moteur miroir, corbeille
│   ├── base.py        (1.1) SQLite : WAL, migrations
│   └── outils.py      (1.1) ffmpeg, ffprobe, fpcalc
├── UI/                (2) gabarits HTML, CSS, JS communs aux pages
├── assets/            config_defaut.toml, versions.toml (fichiers intégrés au paquet)
└── mod/
    ├── analyse/       (1.1) scan, mesures versionnées, lots de tags
    ├── catalogue/     (3.x) MusicBrainz, AcoustID, Wikidata, paroles → base
    ├── ia/            (4.2) traductions, cas ambigus → base
    ├── pages/         (2, 4.1, 5) base → _data
    │   └── modules/   album, artiste, projet, compositeur
    └── copies/        (1.1, #54) baladeur, archivage
```

Les dossiers marqués d'un jalon n'existent pas encore : ils naissent avec le livrable correspondant.

| Couche | Rôle | Peut importer |
|---|---|---|
| `core` | Entrée du programme : lit la ligne de commande, vérifie l'environnement, envoie chaque commande au mod qui la traite. Aucun traitement métier. | tout |
| `mod/<nom>` | Un domaine métier (analyse, catalogue, IA, pages, copies). | `backend`, `UI`, `assets`, lui-même |
| `UI` | Composants d'affichage communs aux pages (gabarits, styles, scripts). | `backend`, `assets` |
| `backend` | Services communs sans métier : configuration, journaux, copie, base SQLite, outils externes. | `assets`, lui-même |
| `assets` | Fichiers intégrés au paquet (pas de code Python), lus par `importlib.resources`. | — |
| racine de `src` | `__versions__.py` : lecteur de `assets/versions.toml`, les versions de la livraison, lisibles par toutes les couches. `__main__.py` : lancement, comme `core`. | rien de `src` (sauf `__main__.py`) |

## Règle de dépendance

- **Un `mod` n'importe jamais un autre `mod`.** Ce qui est partagé remonte dans `backend/` (données, services) ou `UI/` (composants d'affichage).
- **Un `mod` n'importe pas `core`**, et `backend` n'importe ni `core`, ni `UI`, ni `mod` : les dépendances descendent toujours de l'entrée vers les services.
- **Les modules à la racine de `src`** (`__versions__.py`) sont des feuilles : toutes les couches peuvent les importer, eux n'importent rien du paquet. `__versions__.py` n'importe que la bibliothèque standard (`tomllib`), pour qu'un script de CI ou de compilation puisse l'exécuter sans installer le programme.
- `tests/test_architecture.py` lit les `import` de chaque fichier de `src` (y compris ceux faits dans une fonction, et les imports relatifs) et échoue à la moindre entorse. Il vérifie aussi que chaque dossier de `src` est une couche connue.

## Circulation par la base

Les `mod` communiquent **par la base SQLite** : chacun lit ou écrit la base, aucun n'appelle les autres.

```
musique ──► mod/analyse ───┐
web ──────► mod/catalogue ─┼──► base SQLite ──► mod/pages ──► _data
            mod/ia ────────┘
```

- Les pages ne lisent que la base : elles se régénèrent hors ligne à tout moment.
- L'IA est facultative : sans elle, les traductions sont simplement absentes de la base.

## Où ranger un nouveau module

1. **Il lance une commande ou vérifie l'environnement ?** → `core/` (la commande appelle une fonction d'un mod).
2. **Il sert à plusieurs mod, sans règle métier** (accès à la base, appel d'un outil, lecture d'un format) ? → `backend/`.
3. **C'est un composant d'affichage commun à plusieurs pages ?** → `UI/`.
4. **C'est un fichier livré avec le programme, pas du code** ? → `assets/` (et `package-data` le prend déjà).
5. **Sinon, c'est du métier** → le mod du domaine, ou un nouveau dossier `mod/<nom>/` avec son `__init__.py`.

Deux mod ont besoin du même code ? Il remonte dans `backend/` ou `UI/`, jamais d'import croisé. Ils ont besoin des mêmes données ? Elles passent par la base.

Les tests suivent la même arborescence (`tests/backend/`, `tests/core/`, `tests/mod/<nom>/`…) ; les garde-fous qui portent sur tout le dépôt restent à la racine de `tests/`. Deux fichiers de test ne doivent pas porter le même nom, même dans des dossiers différents (pytest les importe sans paquet).
