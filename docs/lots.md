# Lots : valider ce que le bot propose

Toute écriture sur la musique passe par un **lot** que l'opérateur valide (règle 3 de `CLAUDE.md`). Le mécanisme ne demande ni interface ni IA : un explorateur, un tableur et un double-clic. L'application Qt (étape 8), puis l'IA, écriront les mêmes décisions.

Code : `src/backend/lot.py` (format, sans métier) et `src/core/lots.py` (commandes, envoi au mod).

## Contenu d'un lot

Un lot est un dossier, dans `_workspace/_in_review/<lot>/` (le bot a tranché) ou `_workspace/_pending/<lot>/` (le bot pose une question) :

| Fichier | Rôle |
|---|---|
| `_lot.md` | Rapport lisible : ce que le bot propose et pourquoi, ou la question posée |
| `_lot.json` | Manifeste : mod, opération, date, version du programme, actions, lignes déjà traitées |
| `_decisions.csv` | Une ligne par action, à remplir dans Excel |
| `traiter.bat` | Lance `disco lot` sur le dossier d'un double-clic |
| copies | Fichiers retravaillés éventuels (règle 2 : conversion, fusion…) |

## `_decisions.csv`

Colonnes : `id;action;before;after;reason;decision;comment`. Le fichier est en UTF-8 avec BOM et séparé par des `;`, pour qu'Excel en français l'ouvre directement avec les accents. Les en-têtes et les valeurs sont **neutres, en anglais** : un lot préparé aujourd'hui restera lisible si la langue du programme change (#56).

Seules deux colonnes se remplissent :

- `decision` : `yes` (ou `oui`, `o`, `y`) pour appliquer, `no` (ou `non`, `n`) pour refuser, vide pour laisser la ligne en attente. Toute autre valeur arrête le traitement, avec la ligne en cause. Il n'y a pas de « tout accepter » : valider demande d'écrire `yes` ;
- `comment` : texte libre, gardé dans le journal avec la décision. Dans `_pending`, c'est la réponse à la question du bot.

Avant toute action, le fichier est relu et validé : en-tête intact, identifiants connus, sans doublon ni ligne supprimée, colonnes `action`, `before`, `after` et `reason` inchangées. Un fichier réenregistré par Excel en « CSV (séparateur : point-virgule) » (encodage Windows, sans BOM) est accepté : les caractères qu'Excel a remplacés par `?` ne comptent pas comme une modification.

Conseil pour les mods : écrire `before` et `after` avec leur unité (`-7.52 dB`), pour qu'Excel ne les prenne pas pour des nombres et ne les réécrive pas (`-7,52`).

## `traiter.bat`

Il ne contient aucune logique : le chemin de `disco.exe` (`paths.bot`, au moment de créer le lot), puis `disco lot` sur son propre dossier. Si `_bot` a été déplacé depuis, il l'affiche et donne la commande à lancer à la main. Il est généré dans `_workspace`, jamais versionné. Sous Linux, ou depuis un terminal, `disco lot <dossier>` fait la même chose.

## Commandes

- **`disco lot <dossier ou nom>`**
  - **dans `_in_review`** : applique les lignes à `yes`, journalise les lignes à `no` comme refusées, avec l'avis. Avant d'appliquer une ligne, le mod relit l'état réel du fichier : s'il ne correspond plus à `before`, le fichier a changé depuis la préparation, la ligne est refusée d'office et signalée. L'application est **partielle** : les lignes vides restent en attente et le lot reste dans `_in_review` ; une ligne déjà traitée n'est jamais appliquée deux fois (le manifeste la note) ;
  - **dans `_pending`** : relance la passe du mod avec les réponses (`comment`). Le lot passe dans `_in_review` avec une proposition (et un `_decisions.csv` neuf), ou reste en attente ;
  - **confirmation avant toute écriture** : un résumé (« 18 ligne(s) à appliquer, 2 refusée(s), 0 en attente ; 3 fichier(s) partiront dans la corbeille »), puis `Appliquer ? (o/N)`, non par défaut.
- **`disco review`** : liste les lots de `_in_review` et `_pending`, avec les lignes décidées, restantes et déjà traitées.
- **`disco reject <lot>`** : refuse d'un coup toutes les lignes restantes, après confirmation.

Chaque passe écrit son journal (`_bot/_log`) et son rapport (`_workspace/_reports`), comme toute opération (`src.backend.oplog`).

## Corbeille

Rien n'est supprimé (règle 5) :

- **ce que le lot retire de la discothèque** (original remplacé par sa copie retravaillée, fichier brut de `_sort` une fois sa version rangée) part dans `_bin`, dans un lot de corbeille `<lot>_<horodatage>`, juste avant que le mod n'applique les lignes ;
- **un lot entièrement traité** (plus aucune ligne en attente, ou refusé en entier) part lui aussi dans `_bin`, en entier, dans un lot séparé `<lot>_done`. La trace complète reste dans les journaux et les rapports.

## Pour un mod : préparer et appliquer ses lots

Le mod prépare un lot avec `src.backend.lot.create(...)` (dans `cfg.in_review` ou `cfg.pending`, exe : `lot.program_path(cfg.bot)`), puis y ajoute ses copies. Il s'inscrit dans le registre `MODS` de `src/core/lots.py` avec un module qui fournit :

| Fonction | Rôle |
|---|---|
| `current(action, cfg) -> str` | État réel, comparé à `action.before` juste avant d'appliquer |
| `to_trash(action, cfg) -> list[Path]` | Fichiers que l'action retire de la discothèque (sous `paths.root`), mis à la corbeille par le cadre |
| `apply(actions, folder, cfg, log) -> dict[str, str]` | Applique les lignes acceptées avec les garanties de la règle 3 (sauvegarde des tags, empreinte audio avant et après, `journal.csv`, script d'annulation) ; renvoie les échecs |
| `rework(folder, answers, cfg, log) -> list[Action] \| None` | Nouvelle passe d'un lot de `_pending` avec les réponses ; une proposition, ou None |

Une ligne en échec, ou un mod qui s'arrête sur une erreur imprévue, est notée `failed` dans le manifeste : elle n'est jamais réessayée automatiquement, le journal et le script d'annulation du mod permettent de vérifier.

L'analyse seule ne modifie rien et ne produit pas de lot : ce sont les traitements qui suivent (tags ReplayGain #21, conventions #82, rangement de `_sort` #78) qui s'inscriront. Après #32, les décisions seront aussi écrites dans la base ; le CSV restera un format d'import et d'export.
