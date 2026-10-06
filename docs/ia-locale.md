# Besoin : IA locale pour le projet « discothèque »

À estimer avec le matériel décrit dans le projet « Setup ».

## Contexte
Des scripts Python locaux vont analyser la discothèque et les discographies, puis produire les fiches d'achat. Les tâches lourdes n'ont pas besoin d'IA :
- lecture des fichiers audio (ffprobe ou mutagen) ;
- appels à l'API MusicBrainz ;
- comparaison de tracklists ;
- génération des pages HTML.

Le processeur, un peu de RAM et quelques Go de disque suffisent. L'IA locale ne sert que pour quelques cas ambigus, pour ne plus consommer de crédits Claude.

## Ce qu'on demanderait au modèle
| Tâche | Taille de l'entrée | Sortie | Difficulté |
|---|---|---|---|
| Cette sortie ne contient-elle que des reprises ? | tracklist + crédits (< 2 000 tokens) | oui / non + justification (JSON) | faible |
| Que contient de plus une édition deluxe ? | 2 tracklists (< 3 000 tokens) | inédits / lives / remix (JSON) | faible |
| Quel est le bon artiste parmi des homonymes ? | tags du dossier + fiches candidates | choix + confiance | moyenne |
| Extraire les infos d'une page web (Qobuz, Wikipédia) | 5 000 à 30 000 tokens de texte | JSON structuré | moyenne à élevée (demande du contexte) |
| Agent qui cherche seul sur le web | long, en plusieurs étapes | fiche complète | élevée, et c'est ce qui coûte cher chez Claude |

Volume : l'ensemble des artistes pour la passe initiale, soit quelques milliers de requêtes courtes. Ensuite, quelques dizaines par semaine. La rapidité n'est pas critique : la tâche peut tourner la nuit.

## Paliers de matériel (ordres de grandeur, modèles quantifiés en Q4)
- **Petit modèle, environ 7 à 9 Md de paramètres.** Environ 6 à 8 Go de VRAM, ou le processeur avec 16 Go de RAM (lent mais utilisable la nuit). Suffisant pour les deux premières tâches, avec une sortie en JSON imposée.
- **Modèle moyen, environ 14 Md.** Environ 10 à 12 Go de VRAM. Plus fiable pour les homonymes et l'extraction de pages courtes.
- **Modèle environ 30 Md, ou MoE (mélange d'experts).** Environ 20 à 24 Go de VRAM ; certains MoE tournent correctement avec processeur et 32 Go de RAM. C'est le palier conseillé pour l'extraction de pages longues et un peu d'autonomie.
- **70 Md et plus.** 40 Go de VRAM ou plus. Nécessaire seulement pour viser le niveau de l'agent Claude actuel, ce qui n'est pas indispensable ici.

Contexte : prévoir au moins 16 000 tokens pour l'extraction de pages web. Plus de contexte consomme de la VRAM ou de la RAM en plus.

## Logiciels à envisager
- Moteur : Ollama, LM Studio ou llama.cpp. Tous fonctionnent sous Windows, exposent une API locale compatible OpenAI et savent imposer une sortie JSON.
- Familles de modèles ouverts à comparer : Qwen, Mistral, Llama, Gemma. Les versions évoluent vite, il faut vérifier les plus récentes au moment de l'installation.
- Le reste de la chaîne : Python 3, ffmpeg (ffprobe), mutagen, requests.

## Questions pour le projet Setup
1. Quelle carte graphique (et combien de VRAM), quelle RAM, quel processeur sur la machine qui héberge la discothèque ?
2. La discothèque doit passer à terme sur un serveur : l'IA tournera-t-elle sur ce serveur ou sur le PC principal ?
3. Faut-il pouvoir laisser tourner la nuit (consommation, bruit) ?
4. Quel palier ci-dessus est atteignable, et pour quel modèle concret ?
