import sys
import html

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
    QInputDialog,
    QDialog,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from .ollama_client import OllamaClient
from .chat_worker import ChatWorker
from .file_utils import read_text_file
from . import memory_manager
from . import template_manager


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
        self.current_conversation_path = None  # fichier .txt de la conversation en cours
        self.active_template_name: str | None = None  # nom du template actif, si un est appliqué
        self.active_template_path = None  # chemin du fichier template actif

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

        self.new_conv_button = QPushButton("🆕 Nouvelle conversation")
        self.new_conv_button.clicked.connect(self._new_conversation)
        top_bar.addWidget(self.new_conv_button)

        self.history_button = QPushButton("📂 Historique")
        self.history_button.clicked.connect(self._open_history)
        top_bar.addWidget(self.history_button)

        self.template_button = QPushButton("📋 Modèles")
        self.template_button.clicked.connect(self._open_templates)
        top_bar.addWidget(self.template_button)

        layout.addLayout(top_bar)

        self.active_template_label = QLabel("")
        self.active_template_label.setStyleSheet("color: #3a6; font-style: italic;")
        self.active_template_label.setVisible(False)
        layout.addWidget(self.active_template_label)

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

    def _new_conversation(self, keep_template: bool = False):
        self.messages = []
        self.current_conversation_path = None
        self.chat_display.clear()
        self._clear_attachment()
        if not keep_template:
            self._set_active_template(None, None)
        elif self.active_template_path and self.active_template_path.exists():
            # On réapplique le system prompt du template en tête de la nouvelle conversation
            self.messages.append(
                {"role": "system", "content": template_manager.load_template(self.active_template_path)}
            )

    def _open_history(self):
        conversations = memory_manager.list_conversations()
        if not conversations:
            QMessageBox.information(self, "Historique", "Aucune conversation sauvegardée pour l'instant.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Historique des conversations")
        dialog.resize(450, 350)
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget()
        for path, label in conversations:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        buttons_row = QHBoxLayout()
        resume_button = QPushButton("Reprendre")
        delete_button = QPushButton("🗑️ Supprimer")
        buttons_row.addWidget(resume_button)
        buttons_row.addWidget(delete_button)
        layout.addLayout(buttons_row)

        def do_resume():
            item = list_widget.currentItem()
            if item is None:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
            dialog.accept()
            self._load_conversation(path)

        def do_delete():
            item = list_widget.currentItem()
            if item is None:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
            confirm = QMessageBox.question(
                dialog,
                "Confirmer la suppression",
                f"Supprimer définitivement cette conversation ?\n\n{item.text()}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            memory_manager.delete_conversation(path)

            # Si la conversation supprimée est celle actuellement ouverte, on repart à zéro
            if self.current_conversation_path == path:
                self._new_conversation()

            list_widget.takeItem(list_widget.row(item))
            if list_widget.count() == 0:
                dialog.accept()

        resume_button.clicked.connect(do_resume)
        delete_button.clicked.connect(do_delete)
        list_widget.itemDoubleClicked.connect(lambda _: do_resume())

        dialog.exec()

    def _text_to_safe_html(self, text: str) -> str:
        """Échappe le HTML et convertit les retours à la ligne en <br> pour un affichage fidèle."""
        return html.escape(text).replace("\n", "<br>")

    def _load_conversation(self, path):
        self.messages = memory_manager.load_conversation(path)
        self.current_conversation_path = path
        self.chat_display.clear()

        for msg in self.messages:
            if msg["role"] == "user":
                self._append_chat(f"<b>Toi :</b> {self._text_to_safe_html(msg['content'])}")
            else:
                self._append_chat(f"<b>Locia :</b> {self._text_to_safe_html(msg['content'])}")
                self.chat_display.append("")

    def _set_active_template(self, name: str | None, path):
        self.active_template_name = name
        self.active_template_path = path
        if name:
            self.active_template_label.setText(f"📋 Modèle actif : {name}")
            self.active_template_label.setVisible(True)
        else:
            self.active_template_label.setVisible(False)

    def _open_templates(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Gestion des modèles de situation")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget()

        def refresh_list():
            list_widget.clear()
            for path, name in template_manager.list_templates():
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                list_widget.addItem(item)

        refresh_list()
        layout.addWidget(list_widget)

        buttons_row = QHBoxLayout()
        new_button = QPushButton("➕ Nouveau")
        edit_button = QPushButton("✏️ Modifier")
        apply_button = QPushButton("✅ Appliquer")
        delete_button = QPushButton("🗑️ Supprimer")
        for b in (new_button, edit_button, apply_button, delete_button):
            buttons_row.addWidget(b)
        layout.addLayout(buttons_row)

        def edit_template(existing_path=None, existing_name=""):
            name, ok = QInputDialog.getText(dialog, "Nom du modèle", "Nom :", text=existing_name)
            if not ok or not name.strip():
                return
            existing_content = template_manager.load_template(existing_path) if existing_path else ""
            content, ok = QInputDialog.getMultiLineText(
                dialog,
                "Contenu du modèle",
                "Décris la situation / le rôle que Locia doit adopter :",
                existing_content,
            )
            if not ok:
                return

            # Si on renomme, on supprime l'ancien fichier pour éviter les doublons
            if existing_path and existing_path.stem != name.strip():
                template_manager.delete_template(existing_path)

            template_manager.save_template(name.strip(), content)
            refresh_list()

        def do_new():
            edit_template()

        def do_edit():
            item = list_widget.currentItem()
            if item is None:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
            edit_template(existing_path=path, existing_name=item.text())

        def do_apply():
            item = list_widget.currentItem()
            if item is None:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
            name = item.text()

            if self.messages:
                confirm = QMessageBox.question(
                    dialog,
                    "Nouvelle conversation requise",
                    "Appliquer un modèle démarre une nouvelle conversation.\nContinuer ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return

            self._new_conversation(keep_template=False)
            self._set_active_template(name, path)
            self.messages.append({"role": "system", "content": template_manager.load_template(path)})
            dialog.accept()

        def do_delete():
            item = list_widget.currentItem()
            if item is None:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
            confirm = QMessageBox.question(
                dialog,
                "Confirmer la suppression",
                f"Supprimer définitivement le modèle « {item.text()} » ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            template_manager.delete_template(path)
            if self.active_template_path == path:
                self._set_active_template(None, None)
            refresh_list()

        new_button.clicked.connect(do_new)
        edit_button.clicked.connect(do_edit)
        apply_button.clicked.connect(do_apply)
        delete_button.clicked.connect(do_delete)
        list_widget.itemDoubleClicked.connect(lambda _: do_apply())

        dialog.exec()

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
        safe_text = self._text_to_safe_html(text)
        if self.pending_attachment:
            content_for_model = f"{self.pending_attachment}\n\n{text}".strip()
            self._append_chat(f"<b>Toi :</b> {safe_text} <i>[📎 {html.escape(self.pending_attachment_name)}]</i>")
        else:
            self._append_chat(f"<b>Toi :</b> {safe_text}")

        self.messages.append({"role": "user", "content": content_for_model})
        self.input_field.clear()
        self._clear_attachment()

        self._set_input_enabled(False)
        self.chat_display.append("")  # force un saut de ligne avant la réponse
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

        # Sauvegarde de l'échange dans le fichier de la conversation en cours
        if self.current_conversation_path is None:
            self.current_conversation_path = memory_manager.new_conversation_path()
        last_user_msg = self.messages[-2]["content"]  # message user juste avant cette réponse
        memory_manager.append_exchange(
            self.current_conversation_path, last_user_msg, full_text
        )

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
