"""
dap.py - Baladeur et sauvegarde froide

Description:
    Copies de sécurité : baladeur (DAP) et sauvegarde froide sur un autre disque.

    Baladeur :
    - `recuperer` : déplace le dossier d'arrivées du DAP (`_sort`) vers celui de la
      discothèque ;
    - `envoyer`   : copie la discothèque en miroir vers le DAP, **sans** les dossiers
      système « _… » de la racine ni le lanceur ;
    - `synchro`   : `recuperer` puis `envoyer` (l'opération habituelle) ;
    - `restaurer` : sens inverse, DAP → discothèque. Ce qui disparaîtrait de la
      discothèque part dans la corbeille. Simulation tant que `--confirmer` n'est pas
      donné.

    Sauvegarde froide :
    - `envoyer`   : miroir de toute la racine (y compris `_data`, `_bot`, `_log`…) sauf
      la corbeille ; côté sauvegarde, les fichiers supprimés ou remplacés sont gardés
      dans sa propre corbeille datée ;
    - `restaurer` : sens inverse, sans `_bot` (l'installation en cours d'exécution) ni
      la corbeille. Simulation tant que `--confirmer` n'est pas donné.

    Chaque opération écrit un journal dans `_log` (affiché aussi dans la console) et un
    rapport lisible dans `_reports`.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.07
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from disco import copie
from disco.config import Config, ErreurConfig
from disco.journal import Journal, ecrire_rapport, horodatage

NOM_LANCEUR = "synchro_discotheque.cmd"


def _go(octets: int) -> str:
    """Volume lisible, en gigaoctets décimaux (« 1.25 Go »)."""
    return f"{octets / 1e9:.2f} Go"


def _verifier_dossier(chemin: Path | None, quoi: str) -> Path:
    """Vérifie qu'un dossier est configuré et présent (baladeur branché, disque monté…).

    Args:
        chemin: Dossier à vérifier, ou None s'il n'est pas configuré.
        quoi: Nom du dossier dans le message d'erreur (« Baladeur », « Sauvegarde »…).

    Returns:
        Le dossier, en `Path`.

    Raises:
        ErreurConfig: Le chemin n'est pas configuré, ou le dossier est introuvable.
    """
    if chemin is None:
        raise ErreurConfig(f"{quoi} : chemin non configuré (voir config.toml ou --dap).")
    if not Path(chemin).is_dir():
        raise ErreurConfig(f"{quoi} introuvable : {chemin}")
    return Path(chemin)


def _systeme(cfg: Config) -> set[str]:
    """Dossiers système de la racine : déclarés dans la config et présents sur le disque."""
    noms = {p.name for p in (cfg.sortie, cfg.journaux, cfg.rapports, cfg.corbeille, cfg.bot)}
    noms.add(cfg.arrivees.name)
    noms |= copie.exclusions_systeme(cfg.racine)
    return {n for n in noms if n.startswith("_")}


def _rapport(cfg, journal, titre, contexte, plan=None, bilans=(), simulation=False, remarques=None):
    """Écrit le rapport d'une opération de copie dans `chemins.rapports`.

    Args:
        cfg: Configuration chargée.
        journal: Journal de l'opération.
        titre: Titre du rapport.
        contexte: Couples (libellé, valeur) : dossiers source et destination.
        plan: Plan du miroir, s'il y en a un (absent pour une simple récupération).
        bilans: Couples (nom de l'étape, `copie.Bilan`) ; ignorés en simulation,
            où rien n'a été copié.
        simulation: Vrai si rien n'a été modifié ; le contexte le signale.
        remarques: Lignes à signaler en plus (corbeille utilisée…).

    Returns:
        Le chemin du rapport écrit.
    """
    chiffres = []
    if plan is not None:
        chiffres += [
            ("Fichiers nouveaux", str(len(plan.nouveaux))),
            ("Fichiers modifiés", str(len(plan.modifies))),
            ("Fichiers en trop côté destination", str(len(plan.en_trop))),
            ("Volume à copier", _go(plan.octets)),
        ]
    erreurs: list[str] = []
    for nom, b in bilans:
        if simulation:
            continue
        if b.deplaces:
            chiffres.append((f"{nom} : fichiers déplacés", str(b.deplaces)))
        if b.copies or not b.deplaces:
            chiffres.append((f"{nom} : fichiers copiés", f"{b.copies} ({_go(b.octets)})"))
        if b.supprimes:
            chiffres.append((f"{nom} : fichiers supprimés", str(b.supprimes)))
        if b.mis_en_corbeille:
            chiffres.append((f"{nom} : fichiers mis en corbeille", str(b.mis_en_corbeille)))
        erreurs += b.erreurs
    if simulation:
        contexte = [*contexte, ("Mode", "simulation : rien n'a été modifié")]
    return ecrire_rapport(cfg.rapports, journal, titre, contexte, chiffres, erreurs, remarques)


def recuperer(cfg: Config, dap: Path, journal, simulation=False) -> copie.Bilan:
    """Déplace les arrivées du baladeur (`<dap>/_sort`) vers `chemins.arrivees`.

    Un baladeur sans dossier d'arrivées n'est pas une erreur : il n'y a rien à faire.

    Args:
        cfg: Configuration chargée.
        dap: Dossier de musique du baladeur.
        journal: Appelable qui reçoit chaque ligne du journal.
        simulation: Liste ce qui serait déplacé, sans rien modifier.

    Returns:
        Le bilan du déplacement (vide s'il n'y avait rien à récupérer).
    """
    src = Path(dap) / cfg.arrivees.name
    if not src.is_dir():
        journal(f"Pas de dossier d'arrivées sur le baladeur ({src}) : rien à récupérer.")
        return copie.Bilan()
    return copie.deplacer_arrivees(src, cfg.arrivees, journal, simulation)


def envoyer(cfg: Config, dap: Path, journal, simulation=False):
    """Copie la discothèque en miroir vers le baladeur.

    Sont exclus, au premier niveau : les dossiers système de la discothèque et ceux du
    baladeur, ainsi que le lanceur. Les fichiers en trop sur le baladeur sont supprimés
    (pas de corbeille : la discothèque reste la référence).

    Args:
        cfg: Configuration chargée.
        dap: Dossier de musique du baladeur.
        journal: Appelable qui reçoit chaque ligne du journal.
        simulation: Liste ce qui serait fait, sans rien modifier.

    Returns:
        Le couple (`copie.Plan`, `copie.Bilan`) du miroir.
    """
    exclus = _systeme(cfg) | copie.exclusions_systeme(dap) | {NOM_LANCEUR}
    journal("Exclus du miroir (premier niveau) : " + ", ".join(sorted(exclus)))
    return copie.miroir(cfg.racine, dap, exclus, journal, corbeille=None, simulation=simulation)


def operation_dap(
    cfg: Config, sens: str, dap: Path | None = None, simulation=False, confirmer=False, console=True
) -> int:
    """Lance une opération sur le baladeur ; renvoie 0 si tout s'est bien passé.

    Écrit un journal (`dap_<sens>`) et un rapport. Sans `confirmer`, « restaurer »
    tourne toujours en simulation : c'est la seule opération qui écrit dans la
    discothèque, et ce qu'elle y remplace part dans la corbeille.

    Args:
        cfg: Configuration chargée.
        sens: « synchro », « envoyer », « recuperer » ou « restaurer ».
        dap: Dossier de musique du baladeur ; `dap.destination` par défaut.
        simulation: Liste ce qui serait fait, sans rien modifier.
        confirmer: Obligatoire pour appliquer « restaurer ».
        console: Affiche aussi le journal dans la console.

    Returns:
        0 si tout s'est bien passé, 1 si au moins un fichier est en erreur.

    Raises:
        ErreurConfig: Baladeur ou discothèque non configuré ou introuvable.
    """
    dap = _verifier_dossier(dap or cfg.dap, "Baladeur")
    _verifier_dossier(cfg.racine, "Discothèque")
    if sens == "restaurer" and not confirmer:
        simulation = True
    with Journal(cfg.journaux, f"dap_{sens}", console=console) as j:
        j(f"Discothèque : {cfg.racine}")
        j(f"Baladeur    : {dap}")
        contexte = [("Discothèque", str(cfg.racine)), ("Baladeur", str(dap))]
        plan, bilans, remarques = None, [], []
        if sens in ("recuperer", "synchro"):
            bilans.append(("Arrivées", recuperer(cfg, dap, j, simulation)))
        if sens in ("envoyer", "synchro"):
            plan, b = envoyer(cfg, dap, j, simulation)
            bilans.append(("Baladeur", b))
        if sens == "restaurer":
            exclus = _systeme(cfg) | copie.exclusions_systeme(dap) | {NOM_LANCEUR}
            corbeille = cfg.corbeille / f"{horodatage(j.debut)}_restauration_dap"
            plan, b = copie.miroir(dap, cfg.racine, exclus, j, corbeille, simulation)
            bilans.append(("Discothèque", b))
            remarques.append(f"Fichiers retirés ou remplacés dans la discothèque : {corbeille}")
            if simulation and not confirmer:
                remarques.append("Relancer avec --confirmer pour appliquer la restauration.")
        titres = {
            "synchro": "Synchronisation du baladeur",
            "envoyer": "Envoi vers le baladeur",
            "recuperer": "Récupération des arrivées du baladeur",
            "restaurer": "Restauration depuis le baladeur",
        }
        chemin = _rapport(cfg, j, titres[sens], contexte, plan, bilans, simulation, remarques)
        j(f"Rapport : {chemin}")
        return 1 if any(b.erreurs for _, b in bilans) else 0


def operation_sauvegarde(
    cfg: Config, sens: str, simulation=False, confirmer=False, console=True
) -> int:
    """Lance une opération de sauvegarde froide ; renvoie 0 si tout s'est bien passé.

    Écrit un journal (`sauvegarde_<sens>`) et un rapport. Sans `confirmer`,
    « restaurer » tourne toujours en simulation.

    Args:
        cfg: Configuration chargée.
        sens: « envoyer » (discothèque → sauvegarde) ou « restaurer » (l'inverse).
        simulation: Liste ce qui serait fait, sans rien modifier.
        confirmer: Obligatoire pour appliquer « restaurer ».
        console: Affiche aussi le journal dans la console.

    Returns:
        0 si tout s'est bien passé, 1 si au moins un fichier est en erreur.

    Raises:
        ErreurConfig: Sauvegarde ou discothèque non configurée ou introuvable.
    """
    dest = _verifier_dossier(cfg.sauvegarde, "Sauvegarde")
    _verifier_dossier(cfg.racine, "Discothèque")
    if sens == "restaurer" and not confirmer:
        simulation = True
    with Journal(cfg.journaux, f"sauvegarde_{sens}", console=console) as j:
        j(f"Discothèque : {cfg.racine}")
        j(f"Sauvegarde  : {dest}")
        remarques = []
        if sens == "envoyer":
            exclus = {cfg.corbeille.name}
            corbeille = dest / cfg.corbeille.name / f"{horodatage(j.debut)}_sauvegarde"
            # Le journal en cours d'écriture n'est pas sauvegardé (il change pendant la copie)
            plan, b = copie.miroir(
                cfg.racine, dest, exclus, j, corbeille, simulation, ignores={j.chemin}
            )
            remarques.append(
                f"Anciennes versions et fichiers retirés de la sauvegarde : {corbeille}"
            )
            titre, nom = "Sauvegarde froide", "Sauvegarde"
        else:
            exclus = {cfg.corbeille.name, cfg.bot.name}
            corbeille = cfg.corbeille / f"{horodatage(j.debut)}_restauration_sauvegarde"
            plan, b = copie.miroir(dest, cfg.racine, exclus, j, corbeille, simulation)
            remarques.append(f"Fichiers retirés ou remplacés dans la discothèque : {corbeille}")
            if simulation and not confirmer:
                remarques.append("Relancer avec --confirmer pour appliquer la restauration.")
            titre, nom = "Restauration depuis la sauvegarde", "Discothèque"
        contexte = [("Discothèque", str(cfg.racine)), ("Sauvegarde", str(dest))]
        chemin = _rapport(cfg, j, titre, contexte, plan, [(nom, b)], simulation, remarques)
        j(f"Rapport : {chemin}")
        return 1 if b.erreurs else 0


def texte_lanceur() -> str:
    """Contenu du lanceur à poser à la racine du baladeur (fins de ligne Windows)."""
    texte = resources.files("disco").joinpath("modeles", NOM_LANCEUR).read_text("utf-8")
    return texte.replace("\r\n", "\n").replace("\n", "\r\n")


def poser_lanceur(dap: Path) -> Path:
    """Écrit le lanceur à la racine du baladeur (remplace un lanceur existant).

    Args:
        dap: Dossier de musique du baladeur.

    Returns:
        Le chemin du lanceur écrit.

    Raises:
        ErreurConfig: Baladeur non configuré ou introuvable.
    """
    dap = _verifier_dossier(dap, "Baladeur")
    chemin = dap / NOM_LANCEUR
    chemin.write_bytes(texte_lanceur().encode("utf-8"))
    return chemin
