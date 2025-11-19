#!/usr/bin/env python3
"""
Interaktiver Modell-Download
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("🚀 Hugging Face Modell Download")
    print("=" * 40)
    
    # Token eingeben
    print("Geben Sie Ihren Hugging Face Token ein:")
    print("(Zu finden unter: https://huggingface.co/settings/tokens)")
    hf_token = input("Token: ").strip()
    
    if not hf_token:
        print("❌ Kein Token eingegeben")
        return
    
    print(f"🔑 Token erhalten: {hf_token[:10]}...")
    
    # Login
    print("🔐 Anmeldung bei Hugging Face...")
    try:
        result = subprocess.run([
            'huggingface-cli', 'login', '--token', hf_token
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Anmeldung erfolgreich!")
        else:
            print(f"❌ Anmeldung fehlgeschlagen: {result.stderr}")
            return
    except Exception as e:
        print(f"❌ Fehler bei der Anmeldung: {e}")
        return
    
    # Modell auswählen
    models = [
        {
            "name": "Llama-3.2-1B (Klein, 1GB)",
            "repo": "huggingface/Llama-3.2-1B-Instruct-Q4_K_M-GGUF",
            "file": "llama-3.2-1b-instruct-q4_k_m.gguf"
        },
        {
            "name": "Phi-3.5-Mini (Mittel, 2.4GB)", 
            "repo": "microsoft/Phi-3.5-mini-instruct-gguf",
            "file": "Phi-3.5-mini-instruct-Q4_K_M.gguf"
        }
    ]
    
    print("\n📋 Verfügbare Modelle:")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model['name']}")
    
    choice = input("\nWählen Sie ein Modell (1 oder 2): ").strip()
    
    if choice == "1":
        selected = models[0]
    elif choice == "2":
        selected = models[1]
    else:
        print("❌ Ungültige Auswahl")
        return
    
    print(f"\n📥 Lade {selected['name']} herunter...")
    
    # Download
    try:
        Path("models").mkdir(exist_ok=True)
        
        result = subprocess.run([
            'huggingface-cli', 'download',
            selected['repo'],
            selected['file'],
            '--local-dir', 'models',
            '--local-dir-use-symlinks', 'False'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            model_path = Path("models") / selected['file']
            if model_path.exists():
                size_mb = model_path.stat().st_size / (1024*1024)
                print(f"✅ Download erfolgreich! ({size_mb:.1f} MB)")
                
                # Config automatisch updaten
                import yaml
                try:
                    with open("config.yaml", "r") as f:
                        config = yaml.safe_load(f)
                    
                    config["cpu_fallback"]["model_path"] = str(model_path)
                    
                    with open("config.yaml", "w") as f:
                        yaml.dump(config, f, default_flow_style=False)
                    
                    print("✅ config.yaml automatisch aktualisiert!")
                    print("\n🎉 Setup komplett!")
                    print("🧪 Testen Sie jetzt: python npu_chat.py")
                    
                except Exception as e:
                    print(f"⚠️ Config-Update fehlgeschlagen: {e}")
                    print(f"   Manuell eintragen: {model_path}")
            else:
                print("❌ Datei nach Download nicht gefunden")
        else:
            print(f"❌ Download fehlgeschlagen: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Download-Fehler: {e}")

if __name__ == "__main__":
    main()