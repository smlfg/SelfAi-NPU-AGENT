# core/npu_llm_interface.py
import json
from pathlib import Path

# Kritische Abhängigkeit: qai_hub_models.
# Der Benutzer muss sicherstellen, dass diese Bibliothek korrekt installiert ist.
try:
    from qai_hub_models.models._shared.llm.app import ChatApp
    from qai_hub_models.models._shared.llm.model import LLMBase
    QAI_HUB_AVAILABLE = True
except ImportError:
    QAI_HUB_AVAILABLE = False

class NpuLLMInterface:
    """Schnittstelle zur Interaktion mit einem lokalen, NPU-beschleunigten QNN-Modell."""
    def __init__(self, model_path: str):
        if not QAI_HUB_AVAILABLE:
            raise ImportError("Die 'qai_hub_models' Bibliothek wurde nicht gefunden. NPU-Inferenz ist nicht möglich.")

        self.model_path = Path(model_path)
        self.model_name = self.model_path.name
        self.model = self._load_model()

    def _get_model_cls(self):
        """
        Bestimmt die korrekte Modell-Klasse aus qai_hub_models basierend auf dem Modellnamen.
        Dies ist eine entscheidende Anpassung, um das richtige Modell zu laden.
        """
        model_name_lower = self.model_name.lower()
        
        # Diese Logik basiert auf der Analyse von `npu_qnn_chat.py`
        if "deepseek" in model_name_lower:
            try:
                from qai_hub_models.models.deepseek_r1_distill_qwen_7b.model import DeepSeekR1DistillQwen7B as ModelClass
                print("Info: Spezifische DeepSeek-Modellklasse für NPU geladen.")
                return ModelClass
            except ImportError:
                print("Warnung: Fallback auf generische NPU-LLM-Klasse für DeepSeek.")
                return LLMBase
        elif "phi" in model_name_lower:
            try:
                # Versuche, eine passende Phi-Klasse zu finden. Da die Namen variieren, ist dies ein Versuch.
                from qai_hub_models.models.phi_3_5_mini_instruct.model import Phi35MiniInstruct as ModelClass
                print("Info: Spezifische Phi-Modellklasse für NPU geladen.")
                return ModelClass
            except ImportError:
                print("Warnung: Fallback auf generische NPU-LLM-Klasse für Phi.")
                return LLMBase
        else:
            print("Warnung: Unbekanntes NPU-Modell. Verwende generische LLM-Klasse.")
            return LLMBase

    def _load_model(self):
        """Lädt das QNN-Modell mithilfe der QAI Hub ChatApp."""
        if not self.model_path.is_dir() or not (self.model_path / "genai_config.json").exists():
            raise FileNotFoundError(f"QNN-Modellverzeichnis oder genai_config.json nicht gefunden unter: {self.model_path}")

        try:
            model_cls = self._get_model_cls()

            # Die ChatApp ist die primäre Schnittstelle für die Interaktion.
            # Die Parameter basieren auf der Analyse von `npu_qnn_chat.py`.
            app = ChatApp(
                model_cls=model_cls,
                # Das Prompt-Format muss modellspezifisch sein. Dieses hier ist ein gängiges Format.
                get_input_prompt_with_tags=lambda x: f"<|user|>\n{x}<|end|>\n<|assistant|>\n",
                tokenizer=None, # Tokenizer wird normalerweise intern vom Modell geladen
                end_tokens=["<|end|>", "<|endoftext|>", "</s>"]
            )
            print(f"NPU ChatApp für '{self.model_name}' erfolgreich erstellt.")
            return app
        except Exception as e:
            raise RuntimeError(f"Fehler beim Initialisieren der NPU ChatApp: {e}")

    def generate_response(self, system_prompt: str, user_prompt: str, history: list = None) -> str:
        """
        Generiert eine Antwort mit dem NPU-Modell.
        """
        # TODO: System-Prompt und History in den NPU-Aufruf integrieren.
        # Die `generate_output_prompt` Methode aus dem Beispielskript scheint keine direkte
        # Unterstützung für System-Prompts oder eine Nachrichten-History zu haben.
        # Dies ist eine Vereinfachung für den Moment.
        if system_prompt:
            # Behelfslösung: System-Prompt vor die Benutzeranfrage stellen.
            full_prompt = f"System-Anweisung: {system_prompt}\n\nBenutzer-Anfrage: {user_prompt}"
        else:
            full_prompt = user_prompt

        try:
            # Dieser Aufruf basiert auf der Analyse von `npu_qnn_chat.py`.
            # Die Parameter steuern die Inferenz auf dem Gerät.
            response = self.model.generate_output_prompt(
                input_prompt=full_prompt,
                context_length=1024,  # Begrenzt die Länge des Kontexts
                max_output_tokens=512, # Begrenzt die Länge der generierten Antwort
                model_from_pretrained_extra={
                    "eval_mode": "on-device",
                    "target_runtime": "QNN_CONTEXT_BINARY"
                }
            )
            return response if response else "Das NPU-Modell hat keine Antwort generiert."
        except Exception as e:
            print(f"Fehler während der NPU-Textgenerierung: {e}")
            return "Es ist ein Fehler bei der NPU-Generierung der Antwort aufgetreten."

def find_qnn_models(models_dir: Path) -> list[Path]:
    """Findet verfügbare QNN-Modellverzeichnisse durch eine rekursive Suche."""
    qnn_model_paths = []
    if not models_dir.is_dir():
        return []
    
    # Verwende rglob, um rekursiv nach der Konfigurationsdatei zu suchen.
    for config_file in models_dir.rglob("genai_config.json"):
        # Der Pfad zum Modell ist das übergeordnete Verzeichnis der Konfigurationsdatei.
        qnn_model_paths.append(config_file.parent)
        
    return qnn_model_paths
