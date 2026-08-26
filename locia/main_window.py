import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt

from .ollama_client import OllamaClient
from .chat_worker import ChatWorker
from .file_utils import read_text_file


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locia")
        self.resize(800, 600)

        self.client = OllamaClient()
        self.messages: list[dict] = []
        self.worker: ChatWorker | None = None
        self.pending_attachment: str | None = None  # contenu du fichier joint, en attente d'envoi
        self.pending_attachment_name: str | None = None

        self._build_ui()
        self._load_models()

    # ---------- UI ----------

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        # Barre du haut : sélection du modèle
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Modèle :"))
        self.model_selector = QComboBox()
        top_bar.addWidget(self.model_selector, stretch=1)
        self.refresh_button = QPushButton("Rafraîchir")
        self.refresh_button.clicked.connect(self._load_models)
        top_bar.addWidget(self.refresh_button)
        layout.addLayout(top_bar)

        # Zone d'affichage de la conversation
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, stretch=1)

        # Barre de saisie
        input_bar = QHBoxLayout()

        self.attach_button = QPushButton("📎 Joindre")
        self.attach_button.clicked.connect(self._attach_file)
        input_bar.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Écris ton message ici...")
        self.input_field.returnPressed.connect(self._send_message)
        input_bar.addWidget(self.input_field, stretch=1)

        self.send_button = QPushButton("Envoyer")
        self.send_button.clicked.connect(self._send_message)
        input_bar.addWidget(self.send_button)

        layout.addLayout(input_bar)

        # Indicateur du fichier actuellement joint (masqué tant qu'aucun fichier)
        self.attachment_label = QLabel("")
        self.attachment_label.setStyleSheet("color: gray; font-style: italic;")
        self.attachment_label.setVisible(False)
        layout.addWidget(self.attachment_label)

        self.setCentralWidget(central)

    # ---------- Logique ----------

    def _load_models(self):
        try:
            models = self.client.list_models()
        except ConnectionError as e:
            QMessageBox.warning(self, "Ollama introuvable", str(e))
            return

        self.model_selector.clear()
        if models:
            self.model_selector.addItems(models)
        else:
            QMessageBox.information(
                self,
                "Aucun modèle",
                "Aucun modèle trouvé. Installe-en un avec, par exemple :\n"
                "ollama pull qwen2.5:7b",
            )

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir un fichier à joindre",
            "",
            "Fichiers texte/code (*.txt *.md *.py *.js *.ts *.json *.yaml *.yml "
            "*.csv *.html *.css *.java *.c *.cpp *.h *.rs *.go *.rb *.php *.sh "
            "*.xml *.ini *.cfg *.log);;Tous les fichiers (*)",
        )
        if not path:
            return

        try:
            self.pending_attachment = read_text_file(path)
        except ValueError as e:
            QMessageBox.warning(self, "Fichier non pris en charge", str(e))
            return

        self.pending_attachment_name = path.split("/")[-1].split("\\")[-1]
        self.attachment_label.setText(f"📎 {self.pending_attachment_name} (sera joint au prochain message)")
        self.attachment_label.setVisible(True)

    def _clear_attachment(self):
        self.pending_attachment = None
        self.pending_attachment_name = None
        self.attachment_label.setVisible(False)

    def _send_message(self):
        text = self.input_field.text().strip()
        if (not text and not self.pending_attachment) or self.model_selector.count() == 0:
            return

        model = self.model_selector.currentText()

        # Ce que le modèle reçoit inclut le fichier joint ; l'affichage chat reste épuré
        content_for_model = text
        if self.pending_attachment:
            content_for_model = f"{self.pending_attachment}\n\n{text}".strip()
            self._append_chat(f"<b>Toi :</b> {text} <i>[📎 {self.pending_attachment_name}]</i>")
        else:
            self._append_chat(f"<b>Toi :</b> {text}")

        self.messages.append({"role": "user", "content": content_for_model})
        self.input_field.clear()
        self._clear_attachment()

        self._set_input_enabled(False)
        self._append_chat("<b>Locia :</b> ", newline=False)

        self.worker = ChatWorker(self.client, model, self.messages)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished_response.connect(self._on_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_token(self, token: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _on_finished(self, full_text: str):
        self.messages.append({"role": "assistant", "content": full_text})
        self.chat_display.append("")  # saut de ligne pour le prochain échange
        self._set_input_enabled(True)

    def _on_error(self, error_text: str):
        QMessageBox.critical(self, "Erreur", error_text)
        self._set_input_enabled(True)

    def _append_chat(self, html: str, newline: bool = True):
        if newline:
            self.chat_display.append(html)
        else:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.chat_display.setTextCursor(cursor)
            self.chat_display.insertHtml(html)

    def _set_input_enabled(self, enabled: bool):
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if enabled:
            self.input_field.setFocus()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
