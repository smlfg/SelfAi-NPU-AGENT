from pathlib import Path

# Kritische Entscheidung: Wir verwenden llama-cpp-python.
# Der Benutzer muss sicherstellen, dass diese Bibliothek installiert ist,
# z.B. mit: pip install llama-cpp-python. Falls das Paket fehlt, wird der
# Fallback während der Laufzeit übersprungen.

class LocalLLMInterface:
    """Schnittstelle zur Interaktion mit einem lokalen GGUF-Sprachmodell."""
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model = self._load_model()

    def _load_model(self):
        """Lädt das GGUF-Modell vom angegebenen Pfad."""
        try:
            from llama_cpp import Llama
        except ModuleNotFoundError as exc:
            raise ImportError(
                "llama-cpp-python ist nicht installiert. "
                "Installiere es mit 'pip install llama-cpp-python' "
                "oder deaktiviere den CPU-Fallback."
            ) from exc

        if not self.model_path.is_file():
            # Kritisch: Stellen Sie sicher, dass die Datei existiert, bevor Sie versuchen, sie zu laden.
            raise FileNotFoundError(f"Modelldatei nicht gefunden unter: {self.model_path}")
        
        # Entscheidung: Wir laden das Modell mit Standardparametern und deaktivieren das ausführliche Logging.
        # n_ctx definiert die maximale Kontextlänge, die das Modell verarbeiten kann.
        try:
            return Llama(model_path=str(self.model_path), n_ctx=4096, verbose=False)
        except Exception as e:
            # Fängt alle anderen potenziellen Fehler während der Modellinitialisierung ab.
            raise RuntimeError(f"Fehler beim Laden des GGUF-Modells: {e}")

    def generate_response(self, system_prompt: str, user_prompt: str, history: list = None) -> str:
        """
        Generiert eine Antwort unter Berücksichtigung der Konversationshistorie.
        """
        # Entscheidung: Die Historie wird vor der aktuellen Benutzeranfrage eingefügt,
        # um dem Modell den vollen Konversationskontext zu geben.
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            completion = self.model.create_chat_completion(messages)
            return completion['choices'][0]['message']['content']
        except Exception as e:
            print(f"Fehler während der Textgenerierung: {e}")
            return "Es ist ein Fehler bei der Generierung der Antwort aufgetreten."
