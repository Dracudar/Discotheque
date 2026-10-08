# CLAUDE.md : projet Discothèque

Consignes pour Claude (sessions cloud et Claude Code sur le PC). Elles priment sur le `CLAUDE.md` global de Dracudar pour ce dépôt.

## Le projet en bref
Indexer une discothèque personnelle (Windows) et produire des pages HTML :
- **album** (analyses qualité par piste, récap) ;
- **artiste** (livrables d'achat Qobuz, voir la spécification hors dépôt, plus bas) ;
- **projet** (BO, OST, comédies musicales) ;
- **compositeur** (classique).

L'index SQLite fait foi. Les pages sont statiques d'abord, puis servies par un serveur local (phase 7).

Le plan détaillé et chiffré (phases 0 à 7, décisions, risques) est dans le projet Claude « Discographie - Analyse & gestion », document `claude/plan-indexation-fiches.md`. Le résumé des décisions utiles au code est dans `docs/README.md`.

## Dépôt public : aucune donnée de la discothèque, aucun chemin du poste
Le dépôt est **public**. Il contient **uniquement** du code, des tests sur données **fictives** ou synthétiques, et la documentation de mise en place. N'y entrent jamais :
- les noms d'artistes, d'albums ou de pistes, les listes de dossiers, les chiffres de la discothèque ;
- les fiches d'achat, l'index, les extraits de scan, les journaux ;
- les paroles, les pochettes, les spectrogrammes, l'audio ;
- les chemins du poste (lecteurs, dossiers) : ils sont dans `config.toml`. Les exemples utilisent le lecteur fictif `X:`.

Le test `tests/test_depot_propre.py` bloque les types de fichiers concernés et les chemins de lecteur réels. Pour le reste, c'est une règle de relecture : un exemple dans le code ou la doc utilise un nom inventé.

Les références réelles restent sur le poste, et leurs emplacements dans `config.toml` (`[references]`) :
- **spécification des fiches d'achat** : à côté des fiches, avec une copie dans le projet Claude (`claude/specification-fiches.md`) ;
- **fiches réelles**, pour les tests locaux (`fiches_achat`, ou la variable `DISCO_FICHES_REF`) ;
- **résultats et scripts de l'audit** de septembre 2026 (`audit`), référence des algorithmes à réécrire.

Les emplacements réels du poste de Dracudar sont notés dans le document d'état du projet Claude, pas ici.

## Architecture du code
Détail dans `docs/ARCHITECTURE.md` (même convention que Morphoz_SnackApp, branche `Refactor`) :
- **`src/` est le paquet** (pas de sous-dossier `disco`) : `from src.backend.config import charger`. La commande reste `disco`, `python -m src` en est l'équivalent ;
- **couches** aux noms anglais : `core/` (entrée : cli, doctor, version), `backend/` (services communs sans métier : config, journal, copie, puis base SQLite et outils), `UI/` (affichage commun aux pages), `assets/` (fichiers intégrés), `mod/<nom>/` (métier : analyse, catalogue, ia, pages, copies). Dossiers métier et code en français ;
- **règle de dépendance** : un `mod` n'importe jamais un autre `mod` ni `core` ; `backend` n'importe ni `core`, ni `UI`, ni `mod`. Ce qui est partagé remonte dans `backend/` ou `UI/`. Vérifié par `tests/test_architecture.py` ;
- **les `mod` communiquent par la base SQLite** : chacun lit ou écrit la base, aucun n'appelle les autres. Les pages ne lisent que la base ;
- **tests en miroir de `src/`** (`tests/backend/`, `tests/mod/copies/`…), sans deux fichiers de même nom.

## Règles absolues (sécurité de la discothèque)
1. **La discothèque (`chemins.racine` en production) est en lecture seule.** Exceptions :
   - les données générées (`_data`) : les pages peuvent être effacées et régénérées à tout moment, **pas la base** (`_data/_base`), coûteuse à reconstruire ;
   - les **lots de tags validés** (ReplayGain, rangement de `_sort`), **lancés par Dracudar depuis son PC**, jamais depuis une session cloud.
2. **L'audio n'est jamais modifié.** Seuls les tags peuvent l'être, par lots.
3. **Toute écriture sur la musique passe par un lot :**
   - une liste validée par Dracudar ;
   - une sauvegarde des tags avant ;
   - une empreinte audio vérifiée avant et après ;
   - un journal (`journal.csv`) ;
   - un script d'annulation.
4. **Le développement se fait sur une copie de travail (sandbox)** : en développement, `chemins.racine` pointe vers elle.
5. **Rien n'est supprimé directement.** Ce qui doit disparaître va dans `chemins.corbeille\<lot>\`, que seul Dracudar vide.
6. Les catégories `vrac` (`Bulk` par défaut, `Night` déclaré dans `_bot`) ne sont jamais réorganisées : elles sont indexées et analysées, sans pages.

## Racine et configuration (`config.toml`, non versionné)
Tout part de la racine de la discothèque (`chemins.racine`) : la sandbox en développement, la discothèque elle-même en production. Les dossiers système sont à la racine et commencent par `_` ; chacun peut être déplacé dans la config.

La configuration se superpose en trois couches, la plus haute l'emportant clé par clé (une catégorie peut être ajoutée ou redéfinie clé par clé) :
1. **défaut**, intégrée au programme (`src/assets/config_defaut.toml`) : réglages d'analyse et catégories standard. **Aucun `config.toml` n'est obligatoire** ;
2. **`<racine>/_bot/config.toml`**, facultatif : seulement ce qui diffère (baladeur, sauvegarde, références, catégories en plus) ;
3. **le `config.toml` du clone** (développement) : `racine = …` (la sandbox) et toute surcharge.

Sans `racine` écrite, elle se déduit de `_bot` (son dossier parent) : emplacement de la config, ou, sans aucun fichier, dossier du programme (exe compilé ou `.venv`). `disco config` indique l'origine de chaque valeur.

Ordre de recherche (`src.backend.config.trouver`) : option `--config`, variable `DISCO_CONFIG` (le fichier doit alors exister), `config.toml` à côté du programme (`_bot` en production, le clone en développement), puis `./config.toml`.

| Dossier | Clé | Rôle |
|---|---|---|
| `_data` | `chemins.sortie` | Pages générées (miroir de la discothèque, `index.html` à la racine) ; ses dossiers internes commencent par `_` |
| `_data/_base` | `chemins.base` | Index SQLite. **Jamais effacé** |
| `_data/_cache` | `chemins.cache` | Réponses des services en ligne |
| `_bot` | `chemins.bot` | Installation de production : environnement, version publiée depuis `main`, `config.toml`, outils externes (`tools`). **Distinct du clone de développement** |
| `_sort` | `chemins.arrivees` | Arrivées depuis le baladeur |
| `_log` | `chemins.journaux` | Journaux détaillés (aussi affichés dans la console) |
| `_reports` | `chemins.rapports` | Rapports lisibles des résultats, avec lien vers le journal (Markdown, puis intégrés à l'interface) |
| `_to_delete` | `chemins.corbeille` | Corbeille : ce que les opérations retirent, pour pouvoir annuler |

Autres clés : `dap.destination` (baladeur, pour les commandes lancées depuis le PC), `sauvegarde.destination` (copie froide), `references.*` (données hors dépôt), `outils.*`, `analyse.*`, `categories.*`. Tout dossier `_…` non déclaré dans `categories` est ignoré par l'indexation.

Toute opération du bot écrit un journal dans `_log` et un rapport dans `_reports` (`src.backend.journal`).

On n'écrit jamais un chemin en dur dans le code ni dans la doc : tout passe par la configuration.

## Décisions techniques à respecter
- **Python ≥ 3.13** (3.14 sur le PC). Dépendances limitées à **numpy, scipy, mutagen**. Toute nouvelle dépendance se justifie dans la PR. Pas de pyloudnorm.
- **Outils externes :** ffmpeg / ffprobe, fpcalc (Chromaprint 1.6.1). fpcalc lit le PCM sur l'entrée standard (vérifié par `disco doctor`).
- **Un seul décodage par piste.** Toutes les mesures (intégrité, ReplayGain 2, crêtes échantillon et vraie ×8, DR, écrêtage, spectre, spectrogramme, AcoustID) se nourrissent du même flux.
- **L'index d'abord.** On lit la fiche de la piste avant toute analyse et on ne décode que si :
  - le fichier est nouveau ;
  - l'audio a changé ;
  - une mesure manque ;
  - ou la **version** de l'algorithme d'une mesure a changé.

  Chaque résultat est stocké avec sa version.
- **ReplayGain 2 :**
  - référence −18 LUFS ;
  - crête vraie ×8, écrite dans les tags de crête ;
  - gain album calculé par addition des histogrammes de sonie des pistes, sans re-décoder ;
  - pas de gain album pour les catégories `vrac` (`Bulk`, `Night` ; voir `rg_album` dans la config) ;
  - tag générique `REPLAYGAIN_*` partout, plus `R128_*` pour les Opus si retenu ;
  - on ne réécrit un fichier que si la valeur change.
- **SQLite :** mode WAL, `busy_timeout`, migrations versionnées (`PRAGMA user_version`), un seul écrivain à la fois.
- **Pages :** arborescence miroir dans `_data`, `index.html` + `data.json` par page ; les données sont aussi exportées en `.js` pour fonctionner en `file://`.

## Mode mentor
- **Désactivé par défaut** dans ce dépôt : Claude écrit le code, Dracudar relit les PR. Les descriptions de PR expliquent les choix.
- **Activé pour tout ce qui touche à SQLite** (schéma, requêtes, migrations, concurrence, FTS5, maintenance). Dracudar veut maîtriser SQLite pour d'autres projets :
  - on avance en guidant, en expliquant le pourquoi ;
  - Dracudar écrit ou valide lui-même le SQL ;
  - les notes de cours vont dans `docs/sqlite/`.
- **Activable à la demande** pour toute autre partie : « en mode mentor ».

## Conventions
- **Langue :** code, noms et commentaires en français, sans accents dans les identifiants (`reference_lufs`, `rg_album`), avec accents dans les textes et les docstrings.
- **En-tête des fichiers Python :** chaque nouveau fichier `.py` de `src/` et de `tests/` commence par le bloc d'en-tête commun aux projets de Dracudar (voir un module existant, par ex. `src/backend/copie.py`) :
  ```
  """
  <fichier>.py - <titre court>

  Description:
      <rôle du module>

  Auteur :
      Dracudar

  Version :
      1.0

  Date de création :
      aaaa.mm.jj

  Date de modification :
      aaaa.mm.jj
  """
  ```
  **Chaque fichier a sa propre version**, au format `majeur.mineur` (pas de correctif au niveau du fichier), indépendante de celle du programme. Un nouveau fichier commence à `1.0`. **À chaque modification d'un fichier**, on met à jour sa `Date de modification` (date du jour). Sa `Version` ne change que si son **code** change : le mineur pour une modification (`1.0` → `1.1`), une seule fois par PR ; le majeur pour une réécriture ou un changement de son interface (`1.4` → `2.0`). Une modification qui ne touche pas au code (docstrings, commentaires, en-tête, numéro de version du programme) change la date, pas la version du fichier. Chaque fonction, méthode et classe a une docstring, avec les rubriques `Args:`, `Returns:`, `Raises:` ou `Attributes:` quand elles apportent quelque chose. `tests/test_entetes.py` vérifie la présence de l'en-tête (`src` et `tests`, sous-dossiers compris) et des docstrings (`src`) et le format de la version, mais pas que la date et la version sont à jour : c'est une règle de relecture.
- **Version du programme :** au format `majeur.mineur.correctif`, dans `__version__` de `src/core/version.py`, sa **seule** source : `pyproject.toml` la lit à l'installation (`dynamic`), et `disco --version` l'affiche. La changer est une modification de `version.py` qui ne touche pas à son code : date de modification à jour, version du fichier inchangée (voir ci-dessus).
- **Git :**
  - **`main` = production uniquement.** Rien n'y est poussé ni proposé directement. Seul Dracudar y fusionne `develop` quand il met une version en service.
  - **`develop` = intégration.** Chaque branche de livrable part de `develop` (`phase-1.1/index`), et sa PR vise `develop`. Dracudar la relit et la fusionne.
  - **Chaque PR est reliée à une issue** (`Closes #n` en tête de description). Les PR ne vont pas dans le GitHub Project et n'ont pas de jalon : c'est l'issue liée qui porte le suivi. Chaque issue a un jalon ; on pose les relations utiles (sous-issues, « bloqué par »). Les issues suivent la même règle que le code : aucune donnée de la discothèque ;
  - **une issue qui demande une action à Dracudar lui est assignée.** Pas d'étiquette pour ça ;
  - **priorité dans le champ `Priority` du GitHub Project** (`Urgent`, `High`, `Normal`, `Low`) ; sans valeur, une issue est `Normal`. Pas d'étiquette de priorité. Depuis une session cloud, le Project n'est pas modifiable : Claude indique la priorité proposée en tête de la description de l'issue (``**Priorité : `High`.**``) ;
  - Conventional Commits en français (`feat(analyse): …`, `fix(scan): …`, `docs: …`) ;
  - un tag Git par version mise en production sur `main` (`v0.1` = jalon 1.1) ;
  - ne jamais travailler en même temps sur la même branche depuis le cloud et depuis le PC.
- **Qualité :** `ruff check .`, `ruff format src tests` et `pytest` doivent passer avant toute PR. La CI le vérifie sous Windows (Python 3.14) et Linux (Python 3.13).
- **Tests :** pas de fichiers audio réels dans le dépôt. Les fixtures audio sont synthétiques, générées par ffmpeg pendant les tests. Les fiches réelles, référence du jalon 4.1, restent hors dépôt et sont lues par les tests locaux (`references.fiches_achat` ou `DISCO_FICHES_REF`).
- **`legacy/fiches/` :** l'ancien gabarit des fiches d'achat, gardé pour référence et testé. Les scripts de l'audit restent hors dépôt (`references.audit`) : on s'en inspire pour réécrire proprement dans `src/`.

## Commandes utiles
```
py -3.14 -m venv .venv && .venv\Scripts\activate && pip install -e .[dev]
disco doctor          # vérifie l'environnement (ne modifie rien)
disco config          # affiche la configuration chargée
disco dap synchro --simulation    # synchro du baladeur, sans rien modifier
disco dap envoyer | recuperer     # une seule étape de la synchro
disco dap lanceur                 # pose le lanceur sur le baladeur
disco sauvegarde envoyer          # copie froide sur un autre disque
disco dap restaurer --confirmer          # baladeur → discothèque (sans --confirmer : simulation)
disco sauvegarde restaurer --confirmer   # copie froide → discothèque (idem)
pytest                # tests
ruff check . && ruff format src tests
```
