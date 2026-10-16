# 01. Ouvrir une base SQLite

Dans le projet : `open_db()`, dans [`src/backend/db.py`](../../src/backend/db.py).

## Ce qu'est SQLite

Une base SQLite est **un seul fichier**. Il n'y a pas de serveur à installer ni à lancer : c'est le programme qui lit et écrit ce fichier, à travers la bibliothèque SQLite livrée avec Python (module `sqlite3`). La version de SQLite dépend de Python, et `disco doctor` l'affiche.

## Les trois objets à connaître

| Objet | Comment l'obtenir | Rôle |
|---|---|---|
| **Connexion** | `sqlite3.connect(chemin)` | Ouvre le fichier, et le crée s'il n'existe pas. Les réglages et les transactions sont propres à **chaque** connexion. |
| **Curseur** | `conn.execute("SELECT …")` | Exécute une requête et donne accès aux lignes du résultat. |
| **Transaction** | ouverte par SQLite ou par Python | Un groupe de modifications : soit tout est enregistré (`commit()`), soit rien ne l'est (`rollback()`). |

Lire un résultat :

```python
cur = conn.execute("SELECT nom FROM exemple WHERE id = ?", (1,))
cur.fetchone()    # première ligne, sous forme de tuple : ('Titre',)
cur.fetchall()    # toutes les lignes : [('Titre',), ('Autre',)]
cur.fetchone()[0] # la première valeur de la première ligne : 'Titre'
```

## Les transactions et `autocommit`

Depuis Python 3.12, la connexion a un réglage `autocommit` à trois valeurs :

| Valeur | Comportement |
|---|---|
| `True` | Chaque instruction est enregistrée tout de suite. Aucune transaction n'est ouverte. |
| `False` | **Recommandé.** Une transaction est toujours ouverte : rien n'est enregistré tant qu'on n'a pas fait `commit()`. Après `commit()` ou `rollback()`, une nouvelle s'ouvre aussitôt. |
| `sqlite3.LEGACY_TRANSACTION_CONTROL` (`-1`) | L'ancien comportement, le défaut sans argument, conservé pour la compatibilité. Python ouvre des transactions de façon peu prévisible : à éviter. |

Avec `autocommit=False`, **une écriture non validée est perdue** à la fermeture :

```python
conn.execute("INSERT INTO exemple (nom) VALUES ('Titre')")
conn.commit()   # sans cette ligne, l'insertion disparaît à la fermeture
```

C'est voulu : un traitement interrompu en cours de route ne laisse pas une base à moitié modifiée.

## `with conn:` ne ferme pas la connexion

```python
with conn:      # commit() en sortie normale, rollback() en cas d'exception
    conn.execute(...)
# ici, la connexion est TOUJOURS ouverte
```

Pour fermer la connexion, il faut `conn.close()`, ou `contextlib.closing()`, qui l'appelle même en cas d'erreur :

```python
from contextlib import closing

with closing(sqlite3.connect(chemin)) as conn:
    ...
# ici, la connexion est fermée
```

Sous Windows, un fichier ouvert ne peut être ni supprimé ni déplacé : une connexion oubliée bloque le fichier de la base.

## Les clés étrangères : désactivées par défaut

Une **clé étrangère** déclare qu'une colonne pointe vers une ligne d'une autre table : « une mesure appartient à un fichier qui existe ».

```sql
CREATE TABLE child (parent_id INTEGER REFERENCES parent(id));
```

Par compatibilité avec ses anciennes versions, **SQLite ne vérifie pas** ces liens tant qu'on n'a pas exécuté :

```sql
PRAGMA foreign_keys = ON;
```

Ce réglage n'est pas enregistré dans le fichier : il vaut pour **une connexion**, et il faut le redonner à chaque ouverture. D'où l'intérêt d'ouvrir la base à **un seul endroit** du code (`open_db()`).

Un `PRAGMA` est une commande de réglage propre à SQLite. On en verra d'autres : `user_version` (migrations), `journal_mode` et `busy_timeout` (accès concurrents).

## Le piège de l'ordre

Deux faits se combinent :

1. avec `autocommit=False`, Python ouvre une transaction **dès la connexion** ;
2. pendant une transaction, `PRAGMA foreign_keys` **ne fait rien, sans aucune erreur**.

```python
conn = sqlite3.connect(chemin, autocommit=False)
conn.execute("PRAGMA foreign_keys = ON")   # ignoré : une transaction est déjà ouverte
```

Le bon ordre :

```python
conn = sqlite3.connect(chemin, autocommit=True)   # aucune transaction ouverte
conn.execute("PRAGMA foreign_keys = ON")          # le réglage prend effet
conn.autocommit = False                           # puis transactions explicites
```

Une erreur silencieuse est la pire de toutes : sans le pragma, tout aurait l'air de marcher, mais la base accepterait des lignes orphelines. Le test `test_foreign_key_enforced` le vérifie (voir [02-tester-la-base.md](02-tester-la-base.md)).

## Créer le dossier, mais pas n'importe où

`open_db()` crée le dossier de la base (`_data/_base`), mais **pas** son parent :

```python
db_dir.mkdir(parents=False, exist_ok=True)
```

- `exist_ok=True` : si le dossier existe déjà, ce n'est pas une erreur ;
- `parents=False` : si `_data` manque, `mkdir` lève `FileNotFoundError`.

Pourquoi : si la racine est mal écrite dans la configuration (faute de frappe), `parents=True` créerait en silence toute une arborescence fantôme et une base neuve et vide. Avec `parents=False`, l'erreur arrive tout de suite. C'est le principe du **fail fast** : échouer tôt et bruyamment plutôt que continuer sur une mauvaise base.

## À retenir

- Une connexion = un fichier ouvert ; les réglages (`PRAGMA`) valent pour **cette** connexion.
- `autocommit=False` + `commit()` explicite : rien n'est écrit par accident.
- `PRAGMA foreign_keys = ON` à chaque connexion, **avant** d'ouvrir une transaction.
- `closing()` pour fermer, même en cas d'erreur.
- Ouvrir la base à un seul endroit du code.

Pour approfondir : la doc Python du module `sqlite3` (section « Transaction control via the autocommit attribute ») et la page « SQLite Foreign Key Support » sur sqlite.org.
