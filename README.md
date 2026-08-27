# Locia

Assistant de discussion IA de bureau, basé sur des modèles locaux via [Ollama](https://ollama.com).

## Prérequis

1. **Ollama** installé et lancé : https://ollama.com/download
2. Au moins un modèle installé, par exemple :
   ```bash
   ollama pull qwen2.5:7b
   ```

## Installation

```bash
python -m venv venv
source venv/bin/activate  # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
python run.py
```

## Structure du projet

```
Locia/
├── run.py                    # point d'entrée
├── requirements.txt
├── memoire/                  # conversations sauvegardées (.txt), créé automatiquement
├── template/                 # modèles de situation (.txt), créé automatiquement
└── locia/
    ├── ollama_client.py       # communication HTTP avec Ollama (streaming)
    ├── chat_worker.py         # thread Qt pour ne pas bloquer l'UI pendant la génération
    ├── file_utils.py          # lecture de fichiers texte/code à joindre
    ├── memory_manager.py       # sauvegarde et reprise des conversations
    ├── template_manager.py     # gestion des modèles de situation
    └── main_window.py         # interface graphique (PySide6)
```

## Prochaines étapes possibles

- Persistance de l'historique des conversations (SQLite ou JSON)
- Gestion de plusieurs conversations / onglets
- System prompt configurable
- Rendu Markdown / coloration syntaxique du code dans les réponses
- Paramètres du modèle (température, contexte, etc.)
