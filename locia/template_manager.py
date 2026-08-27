"""
Gestion des templates (situations prédéfinies) dans le dossier 'template/'.

Chaque template = un fichier .txt contenant le texte du "system prompt"
à utiliser en tête de conversation. Le nom du fichier = nom du template.
"""

import re
import sys
from pathlib import Path


def _get_project_root() -> Path:
    """
    Retourne le dossier racine du projet.
    - En exécution normale (python run.py) : dossier parent du package 'locia/'.
    - En exécutable PyInstaller (--onefile) : dossier où se trouve le .exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_template_dir() -> Path:
    """
    Retourne le dossier 'template/' situé à la racine du projet (ou à côté du .exe),
    et le crée s'il n'existe pas.
    """
    template_dir = _get_project_root() / "template"
    template_dir.mkdir(exist_ok=True)
    return template_dir


def _sanitize_filename(name: str) -> str:
    """Nettoie un nom de template pour en faire un nom de fichier valide."""
    safe = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return safe or "template_sans_nom"


def save_template(name: str, content: str) -> Path:
    """Crée ou met à jour un template."""
    path = get_template_dir() / f"{_sanitize_filename(name)}.txt"
    path.write_text(content, encoding="utf-8")
    return path


def load_template(path: Path) -> str:
    """Charge le contenu (system prompt) d'un template."""
    return path.read_text(encoding="utf-8")


def delete_template(path: Path) -> None:
    """Supprime définitivement un template."""
    path.unlink(missing_ok=True)


def list_templates() -> list[tuple[Path, str]]:
    """
    Liste les templates disponibles, triés par ordre alphabétique.
    Retourne des tuples (chemin, nom affichable).
    """
    template_dir = get_template_dir()
    files = sorted(template_dir.glob("*.txt"), key=lambda p: p.stem.lower())
    return [(f, f.stem) for f in files]
