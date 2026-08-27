"""
Gestion de la persistance des conversations dans le dossier 'memoire/'.

Format de fichier (simple, lisible, facilement reparsable) :

    [USER]
    <texte du message utilisateur>
    [ASSISTANT]
    <texte de la réponse>
    [USER]
    ...

Chaque conversation = un fichier .txt, nommé par date/heure de création.
"""

import sys
from datetime import datetime
from pathlib import Path

USER_TAG = "[USER]"
ASSISTANT_TAG = "[ASSISTANT]"
TITLE_TAG = "[TITLE]"


def _get_project_root() -> Path:
    """
    Retourne le dossier racine du projet.
    - En exécution normale (python run.py) : dossier parent du package 'locia/'.
    - En exécutable PyInstaller (--onefile) : dossier où se trouve le .exe,
      et non le dossier temporaire d'extraction (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_memoire_dir() -> Path:
    """
    Retourne le dossier 'memoire/' situé à la racine du projet (ou à côté du .exe),
    et le crée s'il n'existe pas.
    """
    memoire_dir = _get_project_root() / "memoire"
    memoire_dir.mkdir(exist_ok=True)
    return memoire_dir


def new_conversation_path() -> Path:
    """Génère un nouveau chemin de fichier pour une conversation, basé sur l'horodatage."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return get_memoire_dir() / f"conversation_{timestamp}.txt"


def _strip_title_line(raw: str) -> str:
    """Retire la ligne [TITLE] éventuelle en tête de fichier, pour ne garder que les échanges."""
    if raw.startswith(TITLE_TAG):
        _, _, rest = raw.partition("\n")
        return rest
    return raw


def get_conversation_title(path: Path) -> str | None:
    """Retourne le titre personnalisé d'une conversation, ou None si non défini."""
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if raw.startswith(TITLE_TAG):
        first_line, _, _ = raw.partition("\n")
        return first_line[len(TITLE_TAG):].strip()
    return None


def set_conversation_title(path: Path, title: str) -> None:
    """Définit (ou remplace) le titre personnalisé d'une conversation."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    raw = _strip_title_line(raw)
    path.write_text(f"{TITLE_TAG} {title.strip()}\n{raw}", encoding="utf-8")


def append_exchange(path: Path, user_text: str, assistant_text: str) -> None:
    """Ajoute un échange (message utilisateur + réponse) à la fin du fichier."""
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{USER_TAG}\n{user_text}\n{ASSISTANT_TAG}\n{assistant_text}\n")


def load_conversation(path: Path) -> list[dict]:
    """
    Recharge une conversation depuis son fichier .txt
    et retourne la liste de messages au format attendu par Ollama.
    """
    if not path.exists():
        return []

    raw = path.read_text(encoding="utf-8")
    raw = _strip_title_line(raw)
    messages: list[dict] = []

    # Découpe sur les balises, en conservant l'ordre
    parts = raw.split(USER_TAG + "\n")
    for part in parts[1:]:  # le premier split est vide (avant le premier [USER])
        if ASSISTANT_TAG in part:
            user_text, rest = part.split(ASSISTANT_TAG + "\n", 1)
            assistant_text = rest.strip("\n")
            # Le dernier échange peut ne pas avoir de retour à la ligne final propre
            if assistant_text.endswith("\n"):
                assistant_text = assistant_text[:-1]
            messages.append({"role": "user", "content": user_text.rstrip("\n")})
            messages.append({"role": "assistant", "content": assistant_text})
        else:
            # Message utilisateur sans réponse encore enregistrée (cas rare/interrompu)
            messages.append({"role": "user", "content": part.rstrip("\n")})

    return messages


def delete_conversation(path: Path) -> None:
    """Supprime définitivement le fichier de conversation."""
    path.unlink(missing_ok=True)


def list_conversations() -> list[tuple[Path, str]]:
    """
    Liste les conversations sauvegardées, triées de la plus récente à la plus ancienne.
    Retourne des tuples (chemin, libellé affichable).
    """
    memoire_dir = get_memoire_dir()
    files = sorted(
        memoire_dir.glob("conversation_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    results = []
    for f in files:
        title = get_conversation_title(f)
        timestamp = f.stem.replace("conversation_", "").replace("_", " ")
        if title:
            label = f"{title} ({timestamp})"
        else:
            preview = _get_preview(f)
            label = f"{timestamp} — {preview}" if preview else timestamp
        results.append((f, label))
    return results


def _get_preview(path: Path, max_len: int = 40) -> str:
    """Extrait un court aperçu (premier message utilisateur) pour affichage dans la liste."""
    try:
        raw = path.read_text(encoding="utf-8")
        raw = _strip_title_line(raw)
        if USER_TAG in raw:
            first_user = raw.split(USER_TAG + "\n", 1)[1].split(ASSISTANT_TAG)[0].strip()
            first_line = first_user.splitlines()[0] if first_user else ""
            return (first_line[:max_len] + "…") if len(first_line) > max_len else first_line
    except (OSError, IndexError):
        pass
    return ""
