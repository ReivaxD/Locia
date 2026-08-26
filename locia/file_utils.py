"""Lecture de fichiers texte/code à joindre à un message."""

from pathlib import Path

# Extensions considérées comme du texte lisible directement
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".html", ".css", ".java", ".c", ".cpp", ".h", ".rs",
    ".go", ".rb", ".php", ".sh", ".xml", ".ini", ".cfg", ".log",
}

MAX_FILE_CHARS = 20_000  # évite de saturer le contexte du modèle


def read_text_file(path: str) -> str:
    """
    Lit un fichier texte et retourne son contenu, tronqué si nécessaire.
    Lève une exception explicite si le fichier n'est pas lisible en texte.
    """
    p = Path(path)

    if p.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError(
            f"Type de fichier non supporté pour l'instant : {p.suffix or 'sans extension'}\n"
            "Seuls les fichiers texte/code sont pris en charge (txt, py, md, csv, etc.)"
        )

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ValueError(f"Impossible de lire le fichier : {e}")

    truncated = False
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS]
        truncated = True

    header = f"[Fichier joint : {p.name}]"
    if truncated:
        header += " (contenu tronqué)"

    return f"{header}\n```\n{content}\n```"
