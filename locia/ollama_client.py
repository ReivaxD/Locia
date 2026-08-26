"""
Client minimal pour l'API Ollama (http://localhost:11434).

Ollama expose /api/chat pour une conversation avec historique,
avec la possibilité de streamer la réponse token par token.
"""

import json
import requests
from typing import Iterator, Callable

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_NUM_CTX = 8192  # taille du contexte (en tokens) envoyée au modèle


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, num_ctx: int = DEFAULT_NUM_CTX):
        self.base_url = base_url
        self.num_ctx = num_ctx

    def list_models(self) -> list[str]:
        """Retourne la liste des modèles installés localement."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as e:
            raise ConnectionError(
                f"Impossible de contacter Ollama sur {self.base_url}. "
                f"Est-il bien lancé ? (erreur: {e})"
            )

    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        on_token: Callable[[str], None],
    ) -> str:
        """
        Envoie l'historique de conversation au modèle et streame la réponse.

        messages : liste de {"role": "user"/"assistant"/"system", "content": str}
        on_token : callback appelé pour chaque fragment de texte reçu
        Retourne le texte complet de la réponse une fois terminé.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": self.num_ctx,
            },
        }
        full_response = ""
        with requests.post(
            f"{self.base_url}/api/chat", json=payload, stream=True, timeout=120
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("done"):
                    break
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_response += token
                    on_token(token)
        return full_response
