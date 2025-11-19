#!/usr/bin/env python3
"""
Automatische Config-Aktualisierung nach Modell-Download
"""
import yaml
from pathlib import Path

def find_downloaded_model():
    """Finde heruntergeladenes GGUF-Modell"""
    models_dir = Path("models")
    
    # Suche nach GGUF-Dateien
    gguf_files = list(models_dir.rglob("*.gguf"))
    
    if not gguf_files:
        print("❌ Keine GGUF-Dateien gefunden")
        return None
    
    # Wähle größte Datei (meist das Haupt-Modell)
    largest_file = max(gguf_files, key=lambda f: f.stat().st_size)
    size_mb = largest_file.stat().st_size / (1024*1024)
    
    print(f"✅ Gefunden: {largest_file.name} ({size_mb:.1f} MB)")
    return str(largest_file)

def update_config(model_path):
    """Aktualisiere config.yaml"""
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        # Aktualisiere CPU-Fallback
        if "cpu_fallback" not in config:
            config["cpu_fallback"] = {}
        
        config["cpu_fallback"]["model_path"] = model_path
        config["cpu_fallback"]["n_ctx"] = 2048  # Kontext-Größe
        config["cpu_fallback"]["n_gpu_layers"] = 0  # CPU-only
        
        # Speichere Config
        with open("config.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        print(f"✅ config.yaml aktualisiert!")
        print(f"   Modell-Pfad: {model_path}")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Config-Update: {e}")
        return False

def main():
    print("🔧 Automatische Config-Aktualisierung")
    print("=" * 40)
    
    # Finde Modell
    model_path = find_downloaded_model()
    
    if not model_path:
        print("\n💡 Kein GGUF-Modell gefunden. Bitte zuerst herunterladen:")
        print("   huggingface-cli download huggingface/Llama-3.2-1B-Instruct-Q4_K_M-GGUF llama-3.2-1b-instruct-q4_k_m.gguf --local-dir models --local-dir-use-symlinks False")
        return
    
    # Aktualisiere Config
    if update_config(model_path):
        print("\n🎉 Setup komplett!")
        print("🧪 Jetzt testen:")
        print("   python npu_chat.py")
    else:
        print(f"\n⚠️ Manuell in config.yaml eintragen:")
        print(f"   model_path: \"{model_path}\"")

if __name__ == "__main__":
    main()