import sys
import os
from qai_hub_models.models._shared.llm.app import ChatApp as App
from qai_hub_models.models._shared.llm.model import LLMBase, get_tokenizer
from qai_hub_models.models.phi_3_5_mini_instruct.model import Phi35MiniInstruct
from qai_hub_models.utils.base_model import TargetRuntime

# --- Pfad-Korrektur für die Umgebung (falls nötig) ---
# Diese Zeilen sind ein Workaround für die Umgebungsprobleme.
# Sie sollten nicht notwendig sein, wenn die Umgebung korrekt konfiguriert ist.
site_packages_path = '/mnt/c/Users/smlfl/Documents/AI_NPU_AGENT_Projekt/.venv2/lib/python3.12/site-packages'
if site_packages_path not in sys.path:
    sys.path.insert(0, site_packages_path)
# --- Ende Pfad-Korrektur ---

# Modell-ID und zugehörige Funktionen für Phi-3.5-Mini-Instruct
MODEL_ID = "phi_3_5_mini_instruct"
MODEL_CLS = Phi35MiniInstruct # Die spezifische Modellklasse für Phi-3.5
GET_INPUT_PROMPT_WITH_TAGS = Phi35MiniInstruct.get_input_prompt_with_tags
END_TOKENS = Phi35MiniInstruct.end_tokens

# Konfiguration für die Ausführung
EVAL_MODE = "on-device" # Oder "fp" für CPU-Ausführung
CHIPSET = "qualcomm-snapdragon-x-elite"
MAX_OUTPUT_TOKENS = 512 # Maximale Länge der Antwort

def main():
    print(f"Lade LLM ({MODEL_ID}) für {EVAL_MODE} Ausführung...")

    # Tokenizer laden
    tokenizer = get_tokenizer(MODEL_ID)

    # Modell-Instanz vorbereiten
    # Hier wird das Modell geladen und ggf. für die NPU kompiliert
    # Die tatsächliche Modell-Instanz wird innerhalb der App erstellt
    # Wir übergeben die Klasse und die Parameter
    model_from_pretrained_extra = {
        "eval_mode": EVAL_MODE,
        "chipset": CHIPSET,
        "target_runtime": TargetRuntime.QNN_CONTEXT_BINARY # Standard für NPU
    }

    # ChatApp instanziieren
    app = App(
        model_cls=MODEL_CLS,
        get_input_prompt_with_tags=GET_INPUT_PROMPT_WITH_TAGS,
        tokenizer=tokenizer,
        end_tokens=END_TOKENS,
        # seed=42, # Optional, für reproduzierbare Ergebnisse
    )

    print("LLM geladen. Sie können jetzt chatten. Tippen Sie 'exit' zum Beenden.")
    print("--------------------------------------------------------------------")

    while True:
        user_input = input("Du: ").strip()
        if user_input.lower() == 'exit':
            print("Chat beendet.")
            break

        if not user_input:
            continue

        print("AI: ", end="")
        try:
            # Generiere die Antwort
            app.generate_output_prompt(
                input_prompt=user_input,
                context_length=2048, # Beispiel-Kontextlänge
                max_output_tokens=MAX_OUTPUT_TOKENS,
                model_from_pretrained_extra=model_from_pretrained_extra,
            )
            print() # Neue Zeile nach der gestreamten Ausgabe
        except Exception as e:
            print(f"Fehler bei der Generierung: {e}")
            print("Bitte überprüfen Sie, ob AnythingLLM läuft und das Modell korrekt konfiguriert ist.")

if __name__ == "__main__":
    main()
