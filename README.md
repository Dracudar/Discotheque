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
├── Artists/, Compilations/, Soundtrack/…   musique, par catégorie (voir docs/README.md)
├── _bot/                   installation de production (version compilée)
│   ├── disco.exe           programme
│   ├── _internal/          Python et dépendances embarqués
│   ├── tools/              ffmpeg.exe, ffprobe.exe, fpcalc.exe
│   └── config.toml         réglages personnels, facultatif (la racine s'en déduit)
├── _data/                  pages générées, en miroir de la discothèque
│   ├── _base/              index SQLite (jamais effacé : long à reconstruire)
│   └── _cache/             réponses des services en ligne
├── _sort/                  arrivées depuis le baladeur, RIP de CD ou achats numériques (à trier)
├── _log/                   journaux détaillés
├── _reports/               rapports lisibles des opérations
└── _to_delete/             corbeille : ce que les opérations retirent
```

Cette structure et les catégories standard sont intégrées au programme : aucun `config.toml` n'est nécessaire. Chaque emplacement peut être changé dans `config.toml`, qui ne contient que ce qui diffère du défaut ; `disco config` affiche l'origine de chaque valeur (`défaut`, `_bot`, `clone`, `déduit`). Détails dans [`docs/configuration.md`](docs/configuration.md).

## Installation (production, Windows)

> À partir de la première version en production (`v0.1`). D'ici là, le programme ne tourne que depuis le clone de développement (voir plus bas).

La production est une **version compilée**, publiée dans les releases GitHub à chaque version de `main`. Elle contient tout : le programme, Python et ses dépendances, ffmpeg, ffprobe et fpcalc. Rien à installer à côté, pas même Python, et aucune configuration obligatoire : la structure de la racine est fixe et les catégories standard sont intégrées.

1. **Lancer l'installateur** téléchargé depuis la [dernière release](https://github.com/Dracudar/Discotheque/releases/latest) (Windows signale un programme non signé : « Informations complémentaires », puis « Exécuter quand même »).
2. **Choisir le dossier de la discothèque.** Le programme s'installe dans `<racine>\_bot` et crée les dossiers système. Une case permet de créer aussi l'arborescence de musique (`Artists`, `Compilations`…), et un choix permet d'installer un modèle d'IA adapté à la machine.
3. **Personnaliser si besoin** `<racine>\_bot\config.toml` : baladeur, sauvegarde, catégories en plus (voir [`config.example.toml`](config.example.toml)).
4. **Chemins longs** (pages de plus de 260 caractères) : une fois, dans PowerShell lancé en administrateur :
   ```
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
   ```
5. **Vérifier** : `<racine>\_bot\disco.exe doctor`. Tout doit être `[OK]`. Le diagnostic ne modifie rien.

**Mise à jour** : relancer l'installateur de la nouvelle version ; la configuration est conservée. **Désinstallation** : retire le programme seulement, jamais la musique, `_data` ni la configuration.

Sous Linux (dont Raspberry Pi), une archive à décompresser dans `<racine>/_bot`, puis `disco init`.

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
| `main` | **Production uniquement.** Elle ne reçoit que `develop`, quand une version est mise en service, avec un tag (`v0.1`…). Chaque tag produit la version compilée installée dans `_bot`. |

Le suivi se fait dans les issues, les jalons et le GitHub Project du dépôt. Les commits suivent les Conventional Commits, en français (`feat(analyse): …`).

### Mise en place

Le développement se fait sur une **copie de travail de la discothèque** (sandbox), jamais sur la vraie.

1. **Préparer la sandbox** comme une installation de production, sans le programme :
   - `_bot\tools` : `ffmpeg.exe` et `ffprobe.exe` (build Windows *essentials* ou *full* sur [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), dossier `bin`), `fpcalc.exe` ([Chromaprint 1.6.1](https://github.com/acoustid/chromaprint/releases/tag/v1.6.1), `chromaprint-fpcalc-1.6.1-windows-x86_64.zip`). Ils sont trouvés sans configuration ; un autre emplacement peut être donné dans `[outils]` ;
   - `_bot\config.toml` (facultatif) : seulement les réglages personnels, voir [`config.example.toml`](config.example.toml).
2. **Installer Python 3.14** (ou 3.13) depuis [python.org](https://www.python.org/downloads/), cloner le dépôt (la branche `develop` est prise par défaut) et créer l'environnement de développement :
   ```
   git clone https://github.com/Dracudar/Discotheque
   cd Discotheque
   py -3.14 -m venv .venv
   .venv\Scripts\activate
   pip install -e .[dev]
   ```
3. **Créer `config.toml` dans le clone** (jamais versionné), avec au minimum la racine de la sandbox :
   ```toml
   [chemins]
   racine = 'X:\Sandbox\Musique'
   ```
   Le reste vient de la configuration par défaut, puis du `_bot\config.toml` de la sandbox s'il existe. Ce qui est écrit dans le clone l'emporte.
4. **Vérifier** avec `disco doctor`, puis lancer les vérifications à passer avant toute PR :
   ```
   ruff check . && ruff format src tests
   pytest
   ```
   La CI les relance sous Windows (Python 3.14) et Linux (Python 3.13).

Le dépôt ne contient aucune donnée réelle : les tests utilisent des données fictives ou synthétiques. Sur sa propre machine, on peut en plus vérifier les fiches d'achat réelles, lues hors dépôt via `[references] fiches_achat` (ou la variable `DISCO_FICHES_REF`).

### Structure du dépôt

```
Discotheque/
├── src/                        le paquet lui-même (commande « disco », « python -m src »)
│   ├── core/                   entrée : commandes (cli), diagnostic (doctor), version
│   ├── backend/                services communs : configuration, journaux, moteur de copie
│   ├── assets/                 configuration par défaut, lanceur du baladeur
│   └── mod/                    le métier, un dossier par mod
│       └── copies/             baladeur et sauvegarde froide (dap)
├── tests/                      tests pytest, sur données fictives, rangés en miroir de src/
│   ├── fixtures/               fiche d'achat fictive
│   ├── test_architecture.py    garde-fou : règle de dépendance entre couches
│   ├── test_depot_propre.py    garde-fou : aucune donnée réelle ni chemin du poste
│   └── test_entetes.py         garde-fou : en-têtes et docstrings
├── legacy/fiches/              ancien gabarit des fiches d'achat (gen.py, _head.html), pour référence
├── docs/
│   ├── README.md               feuille de route (jalons) et catégories
│   ├── ARCHITECTURE.md         couches du code et règle de dépendance
│   ├── configuration.md        couches, catégories, origines des valeurs
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
