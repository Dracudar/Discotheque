# Discothèque

Outils pour indexer et documenter une discothèque personnelle (fichiers FLAC, ALAC, MP3, AAC, Opus), avec une règle avant tout : **la musique est en lecture seule**. Toute écriture de tags passe par un lot validé, journalisé et réversible.

> **État : jalon 0** (socle). La feuille de route complète est dans [`docs/README.md`](docs/README.md).

## Fonctionnalités

**Disponibles**
- **Diagnostic** (`disco doctor`) : Python, modules, SQLite, ffmpeg, fpcalc, chemins longs et configuration, sans rien modifier.
- **Synchronisation du baladeur** : récupère ses arrivées, puis y copie la discothèque en miroir. Un double-clic sur le lanceur posé sur le baladeur suffit.
- **Copies de sécurité** : sauvegarde froide sur un autre disque, restauration depuis le baladeur ou la sauvegarde. Rien n'est supprimé directement : ce qui disparaît part dans une corbeille.
- **Journaux et rapports** : chaque opération s'affiche dans la console, écrit un journal détaillé et produit un rapport lisible.

**Prévues**
- **Analyses qualité par piste, en un seul décodage** : intégrité, spectre (faux lossless, faux Hi-Res, faux 24 bits), ReplayGain 2 avec crête vraie ×8, plage dynamique, écrêtage, empreinte AcoustID.
- **Pages HTML** par album, artiste, projet (BO, OST, comédies musicales) et compositeur, consultables hors ligne, puis servies par un serveur local.
- **Suivi** des achats (Qobuz) et des nouveautés (MusicBrainz), paroles synchronisées, traductions.

## Organisation de la discothèque

Tout part d'un dossier racine. Les dossiers de musique y sont rangés par catégorie. Les dossiers système commencent par `_` et ne sont jamais copiés sur le baladeur.

```
<racine>/
├── Artists/, Compilations/, Soundtrack/…   musique, par catégorie (voir config.toml)
├── _bot/                   installation de production
│   ├── .venv/              environnement Python
│   ├── tools/              ffmpeg.exe, ffprobe.exe, fpcalc.exe
│   └── config.toml         configuration (la racine s'en déduit)
├── _data/                  pages générées, en miroir de la discothèque
│   ├── _base/              index SQLite (jamais effacé : long à reconstruire)
│   └── _cache/             réponses des services en ligne
├── _sort/                  arrivées depuis le baladeur
├── _log/                   journaux détaillés
├── _reports/               rapports lisibles des opérations
└── _to_delete/             corbeille : ce que les opérations retirent
```

Chaque emplacement peut être changé dans `config.toml`.

## Installation (production, Windows)

L'installation de production vit dans `<racine>\_bot`, à part du clone de développement. Elle utilise la version publiée sur `main`.

1. **Python 3.14** (ou 3.13), depuis [python.org](https://www.python.org/downloads/).
2. **Environnement et programme**, dans `<racine>\_bot` :
   ```
   cd X:\Musique\_bot
   py -3.14 -m venv .venv
   .venv\Scripts\pip install https://github.com/Dracudar/Discotheque/archive/refs/heads/main.zip
   ```
   Pour mettre à jour, relancer la même commande `pip install` avec `--force-reinstall`.
3. **Outils externes**, à copier dans `<racine>\_bot\tools` (aucune installation, aucun PATH à modifier) :

   | Outil | Où le trouver | Fichiers à copier |
   |---|---|---|
   | **ffmpeg / ffprobe** | build Windows *essentials* ou *full* sur [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) | `bin\ffmpeg.exe`, `bin\ffprobe.exe` et `LICENSE` |
   | **fpcalc** (Chromaprint 1.6.1) | [versions de Chromaprint](https://github.com/acoustid/chromaprint/releases/tag/v1.6.1), `chromaprint-fpcalc-1.6.1-windows-x86_64.zip` | `fpcalc.exe` |

   Ils sont trouvés tout seuls. Un autre emplacement peut être donné dans la section `[outils]` de la config.
4. **Configuration** : copier [`config.example.toml`](config.example.toml) en `<racine>\_bot\config.toml` et l'adapter (baladeur, sauvegarde, catégories). La racine s'en déduit : c'est le dossier parent de `_bot`.
5. **Chemins longs** (pages de plus de 260 caractères) : une fois, dans PowerShell lancé en administrateur :
   ```
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
   ```
6. **Vérifier** : `.venv\Scripts\disco doctor`. Tout doit être `[OK]`. Le diagnostic ne modifie rien.
7. **Baladeur** (facultatif) : `.venv\Scripts\disco dap lanceur --dap <dossier de musique du baladeur>` y pose `synchro_discotheque.cmd`.

## Commandes

| Commande | Rôle |
|---|---|
| `disco doctor` | Vérifie Python, les modules, SQLite (FTS5, JSON), ffmpeg, fpcalc (y compris par l'entrée standard), les chemins longs et la configuration |
| `disco config` | Affiche la configuration chargée et l'emplacement de chaque dossier |
| `disco dap synchro` | Déplace les arrivées du baladeur (`_sort`) vers la discothèque, puis copie la discothèque en miroir sur le baladeur, sans les dossiers système `_…` |
| `disco dap envoyer` / `recuperer` | Une seule des deux étapes |
| `disco dap restaurer --confirmer` | Sens inverse, baladeur → discothèque ; ce qui disparaîtrait part dans `_to_delete`. Sans `--confirmer` : simulation |
| `disco dap lanceur --dap <dossier>` | Pose `synchro_discotheque.cmd` sur le baladeur : un double-clic lance la synchro, quelles que soient les lettres de lecteur |
| `disco sauvegarde envoyer` / `restaurer --confirmer` | Copie froide sur un autre disque ; les fichiers remplacés ou supprimés y sont gardés dans sa corbeille |

Toutes les commandes de copie acceptent `--simulation`.

## Développement

### Branches

| Branche | Rôle |
|---|---|
| `develop` | **Branche par défaut**, intégration. Chaque livrable part d'elle (`phase-1.1/index`…) et y revient par une PR reliée à son issue. |
| `main` | **Production uniquement.** Elle ne reçoit que `develop`, quand une version est mise en service, avec une étiquette (`v0.1`…). C'est elle qu'installe `_bot`. |

Le suivi se fait dans les issues, les jalons et le GitHub Project du dépôt. Les commits suivent les Conventional Commits, en français (`feat(analyse): …`).

### Mise en place

Le développement se fait sur une **copie de travail de la discothèque** (sandbox), jamais sur la vraie.

1. Préparer la sandbox comme une installation de production (`_bot\tools`, `_bot\config.toml`), sans forcément y créer de `.venv`.
2. Cloner le dépôt (la branche `develop` est prise par défaut) et installer l'environnement de développement :
   ```
   git clone https://github.com/Dracudar/Discotheque
   cd Discotheque
   py -3.14 -m venv .venv
   .venv\Scripts\activate
   pip install -e .[dev]
   ```
3. Créer `config.toml` dans le clone (jamais versionné), avec au minimum la racine de la sandbox :
   ```toml
   [chemins]
   racine = 'X:\Sandbox\Musique'
   ```
   Le reste est lu dans le `_bot\config.toml` de la sandbox. Ce qui est écrit dans le clone l'emporte.
4. `disco doctor`, puis les vérifications à passer avant toute PR :
   ```
   ruff check . && ruff format src tests
   pytest
   ```
   La CI les relance sous Windows (Python 3.14) et Linux (Python 3.13).

Le dépôt ne contient aucune donnée réelle : les tests utilisent des données fictives ou synthétiques. Sur sa propre machine, on peut en plus vérifier les fiches d'achat réelles, lues hors dépôt via `[references] fiches_achat` (ou la variable `DISCO_FICHES_REF`).

### Structure du dépôt

```
Discotheque/
├── src/disco/                  code du projet (commande « disco »)
│   ├── cli.py                  commandes et options
│   ├── config.py               recherche, lecture et validation de config.toml
│   ├── doctor.py               diagnostic de l'environnement
│   ├── copie.py                moteur de copie miroir (atomique, corbeille, simulation)
│   ├── dap.py                  baladeur et sauvegarde froide
│   ├── journal.py              journaux (_log) et rapports (_reports)
│   └── modeles/
│       └── synchro_discotheque.cmd   lanceur posé sur le baladeur
├── tests/                      tests pytest, sur données fictives uniquement
│   ├── fixtures/               fiche d'achat fictive
│   └── test_depot_propre.py    garde-fou : aucune donnée réelle ni chemin du poste
├── legacy/fiches/              ancien gabarit des fiches d'achat (gen.py, _head.html), pour référence
├── docs/
│   ├── README.md               feuille de route (jalons) et catégories
│   └── ia-locale.md            besoin et matériel pour l'IA locale
├── .github/workflows/ci.yml    CI : ruff, pytest, disco doctor (Windows et Linux)
├── config.example.toml         modèle de configuration (chemins fictifs)
├── pyproject.toml              paquet, dépendances, ruff
├── CLAUDE.md                   consignes pour Claude
└── LICENSE
```

## Confidentialité

Le dépôt est public. Il ne contient ni données de la discothèque (noms, fiches, index, paroles, pochettes, audio), ni chemins de la machine : tout ce qui est propre au poste vit dans `config.toml`, non versionné. Un test bloque l'entrée de ces fichiers et des chemins de lecteur réels.

## Historique des versions

| Version | Date | Description |
|---|---|---|
| — | — | Pas encore de version en production. `v0.1` correspondra au jalon 1.1 (index SQLite et analyses). |

## Auteur et licence

Dracudar. Projet sous licence MIT.
