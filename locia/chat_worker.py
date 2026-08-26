from PySide6.QtCore import QThread, Signal
from .ollama_client import OllamaClient


class ChatWorker(QThread):
    """Exécute l'appel au modèle dans un thread séparé pour garder l'UI fluide."""

    token_received = Signal(str)
    finished_response = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, client: OllamaClient, model: str, messages: list[dict]):
        super().__init__()
        self.client = client
        self.model = model
        self.messages = messages

    def run(self):
        try:
            full_text = self.client.chat_stream(
                model=self.model,
                messages=self.messages,
                on_token=self.token_received.emit,
            )
            self.finished_response.emit(full_text)
        except Exception as e:
            self.error_occurred.emit(str(e))
