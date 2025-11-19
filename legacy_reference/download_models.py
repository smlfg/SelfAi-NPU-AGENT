#!/usr/bin/env python3
"""
Modell-Download-Skript für GGUF-Modelle von Hugging Face
"""
import os
import subprocess
import sys
from pathlib import Path

# Empfohlene GGUF-Modelle (klein bis groß)
RECOMMENDED_MODELS = [
    {
        "name": "Phi-3.5-Mini-Instruct (4B) - Q4_K_M",
        "repo": "microsoft/Phi-3.5-mini-instruct-gguf",
        "file": "Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "size": "~2.4GB",
        "description": "Kleines, schnelles Modell - ideal für Tests"
    },
    {
        "name": "Llama-3.2-3B-Instruct - Q4_K_M", 
        "repo": "huggingface/Llama-3.2-3B-Instruct-Q4_K_M-GGUF",
        "file": "llama-3.2-3b-instruct-q4_k_m.gguf",
        "size": "~1.9GB",
        "description": "Meta Llama 3.2 - sehr gut für Chat"
    },
    {
        "name": "Qwen2.5-7B-Instruct - Q4_K_M",
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF", 
        "file": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "size": "~4.4GB",
        "description": "Alibaba Qwen - sehr gute Qualität"
    }
]

def check_huggingface_cli():
    """Prüfe ob huggingface-cli verfügbar ist"""
    try:
        result = subprocess.run(['huggingface-cli', '--help'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def setup_hf_token():
    """Setup Hugging Face Token"""
    print("🔑 Hugging Face Token Setup")
    print("-" * 40)
    
    token = input("Bitte geben Sie Ihren Hugging Face Token ein: ").strip()
    
    if not token:
        print("❌ Kein Token eingegeben")
        return False
    
    try:
        # Login with token
        result = subprocess.run(['huggingface-cli', 'login', '--token', token],
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Hugging Face Login erfolgreich!")
            return True
        else:
            print(f"❌ Login fehlgeschlagen: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Fehler beim Login: {e}")
        return False

def download_model(model_info):
    """Lade ein spezifisches Modell herunter"""
    print(f"\n📥 Lade {model_info['name']} herunter...")
    print(f"   Repository: {model_info['repo']}")
    print(f"   Datei: {model_info['file']}")
    print(f"   Größe: {model_info['size']}")
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    try:
        # Download mit huggingface-cli
        cmd = [
            'huggingface-cli', 'download',
            model_info['repo'],
            model_info['file'],
            '--local-dir', str(models_dir),
            '--local-dir-use-symlinks', 'False'
        ]
        
        print(f"🔄 Führe aus: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            downloaded_file = models_dir / model_info['file']
            if downloaded_file.exists():
                size_mb = downloaded_file.stat().st_size / (1024*1024)
                print(f"✅ Download erfolgreich! ({size_mb:.1f} MB)")
                return str(downloaded_file)
            else:
                print("❌ Datei nach Download nicht gefunden")
                return None
        else:
            print(f"❌ Download fehlgeschlagen: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Fehler beim Download: {e}")
        return None

def update_config(model_path):
    """Aktualisiere config.yaml mit neuem Modellpfad"""
    try:
        import yaml
        
        # Lade aktuelle Config
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        # Aktualisiere CPU-Fallback Pfad
        if "cpu_fallback" not in config:
            config["cpu_fallback"] = {}
        
        config["cpu_fallback"]["model_path"] = model_path
        
        # Speichere Config
        with open("config.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        print(f"✅ config.yaml aktualisiert mit: {model_path}")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren der Config: {e}")
        return False

def main():
    print("🚀 GGUF Modell Download für NPU/CPU Chat")
    print("=" * 50)
    
    # Prüfe huggingface-cli
    if not check_huggingface_cli():
        print("❌ huggingface-cli nicht gefunden!")
        print("💡 Installieren Sie es mit: pip install huggingface_hub[cli]")
        sys.exit(1)
    
    print("✅ huggingface-cli verfügbar")
    
    # Setup Token
    if not setup_hf_token():
        print("❌ Hugging Face Login fehlgeschlagen")
        sys.exit(1)
    
    # Zeige verfügbare Modelle
    print("\n📋 Verfügbare Modelle:")
    for i, model in enumerate(RECOMMENDED_MODELS, 1):
        print(f"{i}. {model['name']}")
        print(f"   {model['description']}")
        print(f"   Größe: {model['size']}")
        print()
    
    # Benutzer-Auswahl
    try:
        choice = input("Welches Modell möchten Sie herunterladen? (1-3): ").strip()
        choice_idx = int(choice) - 1
        
        if 0 <= choice_idx < len(RECOMMENDED_MODELS):
            selected_model = RECOMMENDED_MODELS[choice_idx]
            
            # Download
            model_path = download_model(selected_model)
            
            if model_path:
                # Config aktualisieren
                if update_config(model_path):
                    print("\n🎉 Setup komplett!")
                    print("💡 Testen Sie jetzt: python npu_chat.py")
                else:
                    print(f"\n⚠️ Modell heruntergeladen, aber Config-Update fehlgeschlagen")
                    print(f"   Manuell eintragen in config.yaml: {model_path}")
            else:
                print("\n❌ Download fehlgeschlagen")
        else:
            print("❌ Ungültige Auswahl")
    
    except (ValueError, KeyboardInterrupt):
        print("\n🛑 Abgebrochen")

if __name__ == "__main__":
    main()