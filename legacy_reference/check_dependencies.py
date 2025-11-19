
import sys
import platform
import importlib.metadata

# --- Configuration ---
MIN_PYTHON_VERSION = (3, 10)
CRITICAL_PACKAGES = {
    "PyYAML": "6.0.2",
    "llama_cpp_python": "0.3.16",
    "httpx": "0.28.1",
    "numpy": None,  # We just check for presence and < 2.0
}
NPU_PACKAGES = {
    "qai_hub_models": None,
}
ARM64_PLATFORM = "aarch64"

# --- Helper Functions ---
def check_python_version():
    """Checks if the current Python version meets the minimum requirement."""
    print(f"--- Checking Python Version ---")
    current_version = sys.version_info
    print(f"Found Python {current_version.major}.{current_version.minor}.{current_version.micro}")
    if current_version >= MIN_PYTHON_VERSION:
        print("✔️ Python version is sufficient.")
        return True
    else:
        print(f"❌ ERROR: Python version {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher is required.")
        return False

def check_platform():
    """Checks the system platform, especially for NPU requirements."""
    print("\n--- Checking System Platform ---")
    machine = platform.machine()
    print(f"Found Platform: {sys.platform}, Architecture: {machine}")
    if machine == ARM64_PLATFORM:
        print("✔️ System is ARM64/aarch64, compatible with NPU acceleration.")
        return True
    else:
        print(f"⚠️ WARNING: System is not ARM64/aarch64. NPU-specific packages may not work as expected.")
        return False

def check_packages(package_list):
    """Checks for the presence and optionally the version of specified packages."""
    all_ok = True
    for pkg, expected_version in package_list.items():
        try:
            version = importlib.metadata.version(pkg)
            if expected_version:
                if version == expected_version:
                    print(f"✔️ {pkg}=={version}")
                else:
                    all_ok = False
                    print(f"❌ {pkg}=={version} (Expected: {expected_version})")
            else:
                # Special check for numpy<2
                if pkg == "numpy" and not version.startswith("1."):
                     all_ok = False
                     print(f"❌ {pkg}=={version} (Expected: <2.0)")
                else:
                    print(f"✔️ {pkg}=={version}")
        except importlib.metadata.PackageNotFoundError:
            all_ok = False
            print(f"❌ {pkg} is not installed.")
    return all_ok

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Dependency Health Check...")
    
    py_ok = check_python_version()
    platform_ok = check_platform()
    
    print("\n--- Checking Core Dependencies ---")
    core_ok = check_packages(CRITICAL_PACKAGES)
    
    print("\n--- Checking NPU Dependencies ---")
    npu_ok = check_packages(NPU_PACKAGES)

    print("\n--- Summary ---")
    if py_ok and core_ok:
        print("✅ Core environment is healthy. CPU fallback is ready.")
    else:
        print("❌ Core environment has issues. Please resolve the errors above.")

    if platform_ok and npu_ok:
        print("✅ NPU environment appears healthy.")
    elif not platform_ok:
        print("⚠️ NPU environment may not be fully functional on this platform.")
    else:
        print("❌ NPU environment has issues. Please resolve the errors above.")

    if not (py_ok and core_ok):
        sys.exit(1)
