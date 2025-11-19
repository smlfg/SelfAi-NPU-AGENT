import os
import sys
import httpx
from config_loader import load_configuration, AppConfig

# --- Check Functions ---

def check_config_loading():
    """Tries to load configuration and secrets. Handles expected errors."""
    print("1. Checking Configuration (.env, config.yaml)...", end=" ")
    try:
        config = load_configuration()
        print("✔️ PASS")
        return config
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ FAIL")
        print(f"   └─ Reason: {e}")
        return None

def check_model_file(config: AppConfig):
    """Checks if the GGUF model file specified in the config exists."""
    print("2. Checking CPU Model File...", end=" ")
    if not config:
        print("SKIPPED (Config failed to load)")
        return False

    model_path = config.cpu_fallback.model_path
    if os.path.exists(model_path):
        print(f"✔️ PASS ({os.path.basename(model_path)} found)")
        return True
    else:
        print(f"❌ FAIL")
        print(f"   └─ Reason: Model file not found at '{model_path}'.")
        print(f"      Please check the 'model_path' in your config.yaml.")
        return False

def check_npu_connectivity(config: AppConfig):
    """Checks if the NPU provider (AnythingLLM) is reachable."""
    print("3. Checking NPU Backend Connectivity...", end=" ")
    if not config:
        print("SKIPPED (Config failed to load)")
        return False

    base_url = config.npu_provider.base_url
    try:
        # We check the health endpoint, which is standard for many servers.
        # If it doesn't exist, we expect a 404, which still means the server is running.
        with httpx.Client() as client:
            response = client.get(base_url, timeout=5.0)
        
        # Allow any status code other than 5xx server errors
        if response.status_code < 500:
            print(f"✔️ PASS (Got status {response.status_code} from {base_url})")
            return True
        else:
            print(f"❌ FAIL")
            print(f"   └─ Reason: NPU backend returned a server error (Status: {response.status_code}).")
            return False

    except httpx.RequestError as e:
        print(f"❌ FAIL")
        print(f"   └─ Reason: Could not connect to '{base_url}'. Is the server running?")
        print(f"      Error: {e}")
        return False

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Running Preflight Checks ---")
    config = check_config_loading()
    model_ok = check_model_file(config)
    npu_ok = check_npu_connectivity(config)
    print("---------------------------------")

    if config and model_ok:
        print("✅ CPU Fallback path is ready.")
    else:
        print("❌ CPU Fallback path has errors.")

    if config and npu_ok:
        print("✅ NPU Primary path seems ready.")
    else:
        print("❌ NPU Primary path has errors.")

    if not all([config, model_ok, npu_ok]):
        print("\nPreflight checks failed. Please resolve the issues above before starting the application.")
        sys.exit(1)
    else:
        print("\nAll preflight checks passed. System is ready.")
