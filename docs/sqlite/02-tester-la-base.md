# 02. Tester du code SQLite avec pytest

Dans le projet : [`tests/backend/test_db.py`](../../tests/backend/test_db.py), qui teste `open_db()`.

## Pourquoi tester

Un test est **une petite fonction qui utilise le code et vérifie que le résultat est celui attendu**. C'est ce qu'on ferait à la main dans un terminal Python, écrit une fois pour toutes et relancé en une commande.

Les tests ne prouvent pas que le code est juste. Ils garantissent qu'une **promesse** du code reste tenue : si quelqu'un (soi-même dans six mois) « simplifie » une ligne et casse quelque chose, un test échoue tout de suite, avec la ligne fautive.

Bonne habitude : **un test par promesse de la docstring**. Pour `open_db()` :

| Promesse | Test |
|---|---|
| crée `_base` et le fichier de la base | `test_creates_db_dir_and_file` |
| active les clés étrangères | `test_foreign_keys_enabled`, `test_foreign_key_enforced` |
| `autocommit=False` : il faut `commit()` | `test_write_lost_without_commit` |
| rouvre une base existante | `test_reopen_keeps_content` |
| lève `FileNotFoundError` si `_data` manque | `test_missing_data_dir_raises` |

## Comment pytest trouve et lance les tests

- Il cherche les fichiers dont le nom commence par `test_` (dans `tests/`, réglé dans `pyproject.toml`).
- Dans ces fichiers, il lance chaque fonction dont le nom commence par `test_`.
- Dans une fonction, **`assert condition`** vérifie que la condition est vraie. Si elle est fausse, le test échoue et pytest affiche les deux valeurs comparées.

```
pytest                              # tous les tests
pytest tests/backend/test_db.py -v  # un fichier ; -v affiche chaque test par son nom
pytest -k foreign                   # seulement les tests dont le nom contient « foreign »
```

## La forme d'un test : préparer, agir, vérifier

```python
def test_reopen_keeps_content(db_dir):
    # Préparer : une base avec une ligne enregistrée
    with closing(open_db(db_dir)) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t (x) VALUES (42)")
        conn.commit()
    # Agir : rouvrir la base
    with closing(open_db(db_dir)) as conn:
        # Vérifier : la ligne est toujours là
        assert conn.execute("SELECT x FROM t").fetchone()[0] == 42
```

Le nom du test dit ce qu'il vérifie : en cas d'échec, `FAILED test_reopen_keeps_content` suffit à savoir ce qui est cassé.

## `tmp_path` : un dossier neuf pour chaque test

```python
def test_exemple(tmp_path):
    data = tmp_path / "_data"
    data.mkdir()
```

`tmp_path` est une **fixture** fournie par pytest : il suffit de l'écrire en paramètre, et pytest passe au test un dossier temporaire vide, différent pour chaque test. On ne touche jamais aux vraies données (ni à la sandbox), et un test ne peut pas en perturber un autre.

## Écrire sa propre fixture

Quand plusieurs tests ont la même étape « préparer », on la met en commun dans une fixture :

```python
@pytest.fixture
def db_dir(tmp_path) -> Path:
    """Dossier _data/_base d'une racine fictive : _data existe, _base pas encore."""
    data = tmp_path / "_data"
    data.mkdir()
    return data / "_base"


def test_foreign_keys_enabled(db_dir):     # pytest appelle db_dir() et passe le résultat
    ...
```

- `@pytest.fixture` est un **décorateur** : une ligne au-dessus d'une fonction qui lui donne un rôle. Ici : « cette fonction prépare quelque chose pour les tests ».
- Un test **demande** une fixture en écrivant son nom en paramètre. pytest l'exécute avant le test et lui passe ce qu'elle **renvoie** (`return`).
- Une fixture peut en utiliser une autre (`db_dir` demande `tmp_path`).
- Chaque test reçoit sa propre copie, préparée à neuf.
- Où la ranger : dans le fichier de test si elle ne sert qu'à lui ; dans `tests/conftest.py` (lu automatiquement par pytest) si plusieurs fichiers en ont besoin.
- Plus tard : avec `yield` au lieu de `return`, une fixture peut aussi **faire le ménage** après le test (par exemple fermer une connexion).

Une fixture ne convient pas à tous les tests : `test_missing_data_dir_raises` a besoin que `_data` **n'existe pas**, il utilise donc `tmp_path` seul.

## Vérifier qu'une erreur est levée : `pytest.raises`

```python
with pytest.raises(FileNotFoundError):
    open_db(tmp_path / "_data" / "_base")
```

Le test réussit seulement si le code dans le bloc lève cette exception. Sans exception, il échoue avec `DID NOT RAISE`.

`match=` vérifie en plus le message (une expression régulière cherchée dans le texte de l'erreur) :

```python
with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
    conn.execute("INSERT INTO child (parent_id) VALUES (99)")
```

Pour trouver quelle exception attendre : lancer le code une fois **sans** `pytest.raises` et lire le nom de l'erreur dans la sortie.

## Fermer les connexions

```python
with closing(open_db(db_dir)) as conn:
    ...
```

Sous Windows, un fichier ouvert ne peut pas être supprimé : une connexion laissée ouverte empêche pytest de nettoyer `tmp_path`, et peut fausser le test suivant. `closing()` ferme même si un `assert` échoue au milieu.

## Tester le comportement, pas seulement un réglage

Lire `PRAGMA foreign_keys` dit que le réglage vaut 1. Cela ne prouve pas que SQLite refuse vraiment une ligne orpheline. Le test le plus convaincant **provoque** la situation :

```python
conn.executescript("""
    CREATE TABLE parent (id INTEGER PRIMARY KEY);
    CREATE TABLE child (parent_id INTEGER REFERENCES parent(id));
""")
conn.execute("INSERT INTO parent (id) VALUES (1)")
conn.execute("INSERT INTO child (parent_id) VALUES (1)")    # accepté : le parent existe
with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
    conn.execute("INSERT INTO child (parent_id) VALUES (99)")  # refusé : aucun parent 99
```

Même idée pour les transactions : `test_write_lost_without_commit` écrit sans `commit()`, rouvre la base et vérifie que la ligne a disparu.

`executescript()` exécute plusieurs instructions SQL séparées par `;` (ici, deux `CREATE TABLE`) ; `execute()` n'en accepte qu'une.

## Un test qui ne peut pas échouer ne protège rien

Après avoir écrit un test, **casser le code exprès** et vérifier que le test échoue. Pour `open_db()`, trois sabotages ont été essayés :

| Sabotage dans `db.py` | Tests qui échouent |
|---|---|
| retirer `PRAGMA foreign_keys = ON` | `test_foreign_keys_enabled` (`assert 0 == 1`), `test_foreign_key_enforced` (`DID NOT RAISE`) |
| `connect(…, autocommit=False)` : le mauvais ordre | les deux mêmes : le pragma est ignoré en silence |
| `mkdir(parents=True)` | `test_missing_data_dir_raises` (`DID NOT RAISE`) |

Puis remettre le code en état (`git checkout -- src/backend/db.py`).

## Lire un échec

```
>       with closing(open_db(db_dir)) as conn:
E       NameError: name 'closing' is not defined
tests\backend\test_db.py:44: NameError
```

- la ligne marquée `>` est celle qui a planté ;
- la ligne `E` donne l'erreur ;
- la dernière ligne donne le fichier et le numéro de ligne.

Pour un `assert` raté, pytest affiche les deux côtés de la comparaison (`assert 0 == 1`) : c'est souvent suffisant pour comprendre.

## Deux pièges rencontrés

- **Redéfinir une valeur du code dans le test** (`DB_NAME = "test.sqlite"` dans le fichier de test) : le test ne vérifie plus le vrai programme. On importe la valeur du code (`from src.backend.db import DB_NAME, open_db`).
- **Oublier un import** : `NameError: name 'closing' is not defined`. Ce que le fichier utilise doit être importé en tête.

## À retenir

- Un test = préparer, agir, vérifier ; un test par promesse.
- `assert` vérifie, `pytest.raises` vérifie une erreur attendue.
- `tmp_path` et les fixtures : chaque test part de zéro, loin des vraies données.
- `closing()` pour toute connexion ouverte dans un test.
- Casser le code exprès pour vérifier que le test sait échouer.

Pour approfondir : la documentation de pytest, pages « Get started », « How to use fixtures » et « How to write and report assertions in tests ».
