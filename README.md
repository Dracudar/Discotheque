# Discothèque

Outils pour indexer et documenter une discothèque personnelle (fichiers FLAC, ALAC, MP3, AAC, Opus) :
- **analyses qualité par piste** en un seul décodage : intégrité, spectre (faux lossless, faux Hi-Res, faux 24 bits), ReplayGain 2 avec crête vraie ×8, plage dynamique, écrêtage, empreinte AcoustID ;
- **pages HTML** par album, artiste, projet (BO, OST, comédies musicales) et compositeur, consultables hors ligne ;
- **suivi** des achats (Qobuz) et des nouveautés (MusicBrainz), paroles synchronisées, traductions ;
- **sécurité d'abord** : la musique est en lecture seule, et toute écriture de tags passe par un lot validé, journalisé et réversible.

Python, SQLite, ffmpeg. Pages statiques d'abord, puis serveur local.

> État : **jalon 0** (socle, configuration, diagnostic, CI). Feuille de route : `docs/README.md`.

## Installation (Windows)

1. **Python 3.14** (ou 3.13), depuis python.org.
2. **ffmpeg / ffprobe** :
   ```
   winget install Gyan.FFmpeg
   ```
3. **fpcalc** (Chromaprint 1.6.1) : télécharger `chromaprint-fpcalc-1.6.1-windows-x86_64.zip` depuis la page des versions de [acoustid/chromaprint](https://github.com/acoustid/chromaprint/releases). Décompresser `fpcalc.exe` dans un dossier du PATH, ou indiquer son chemin dans `config.toml`.
4. **Chemins longs** (pages de plus de 260 caractères) : une fois, dans PowerShell lancé en administrateur :
   ```
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
   ```
5. **Environnement du projet**, dans le clone :
   ```
   py -3.14 -m venv .venv
   .venv\Scripts\activate
   pip install -e .[dev]
   copy config.example.toml config.toml
   ```
   Adapter `config.toml` à la machine : chemins de la discothèque (une copie de travail pendant le développement), de la sortie, des références et du baladeur. Ce fichier n'est jamais versionné.
6. **Vérifier** :
   ```
   disco doctor
   ```
   Tout doit être `[OK]`. Le diagnostic ne modifie rien.

## Commandes

| Commande | Rôle |
|---|---|
| `disco doctor` | Vérifie Python, les modules, SQLite (FTS5, JSON), ffmpeg, fpcalc (y compris par l'entrée standard), les chemins longs et la configuration |
| `disco config` | Affiche la configuration chargée et le traitement de chaque dossier |
| `disco dap synchro` | Déplace les arrivées du baladeur (`_sort`) vers la discothèque, puis copie la discothèque en miroir sur le baladeur, sans les dossiers système `_…` de la racine |
| `disco dap envoyer` / `recuperer` | Une seule des deux étapes |
| `disco dap restaurer --confirmer` | Sens inverse, baladeur → discothèque ; ce qui disparaîtrait part dans `_to_delete`. Sans `--confirmer` : simulation |
| `disco dap lanceur --dap <dossier>` | Pose `synchro_discotheque.cmd` sur le baladeur : un double-clic lance la synchro, quelles que soient les lettres de lecteur |
| `disco sauvegarde envoyer` / `restaurer --confirmer` | Copie froide sur un autre disque ; les fichiers remplacés ou supprimés y sont gardés dans sa corbeille |

Toutes les commandes de copie acceptent `--simulation`. Chacune affiche son déroulement dans la console, l'écrit dans `_log` et produit un rapport lisible dans `_reports`.

## Organisation de la discothèque

```
<racine>/                 dossiers de musique (Artists, Compilations…)
<racine>/_discotheque/    pages générées, index et caches
<racine>/_bot/            installation de production et config.toml
<racine>/_sort/           arrivées depuis le baladeur
<racine>/_log/            journaux détaillés
<racine>/_reports/        rapports lisibles des opérations
<racine>/_to_delete/      corbeille des opérations
```

## Tests

```
pytest
```

Le dépôt ne contient aucune donnée réelle : les tests utilisent des données fictives ou synthétiques. Sur sa propre machine, on peut en plus vérifier les fiches d'achat réelles, lues hors dépôt via `[references] fiches_achat` dans `config.toml` (ou la variable `DISCO_FICHES_REF`).

## Organisation du dépôt

```
src/disco/          code du projet (commande « disco »)
tests/              tests (pytest), sur données fictives ou synthétiques uniquement
legacy/fiches/      ancien gabarit des fiches d'achat (gen.py, _head.html), pour référence
docs/               feuille de route, IA locale
```

## Confidentialité

Le dépôt est public. Il ne contient ni données de la discothèque (noms, fiches, index, paroles, pochettes, audio), ni chemins de la machine : tout ce qui est propre au poste vit dans `config.toml`, non versionné. Un test bloque l'entrée de ces fichiers et des chemins de lecteur réels.

## Licence

MIT.
