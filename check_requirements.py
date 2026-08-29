"""
CogniOS - Automatic Dependency Checker and Graceful Installer.

Checks required packages against requirements.txt (or standard spec)
and gracefully downloads/installs any missing modules automatically.
"""

import sys
import os
import subprocess
import importlib.util

# Map PyPI package names to their Python import module names
PACKAGE_TO_MODULE_MAP = {
    "scikit-learn": "sklearn",
    "python-dotenv": "dotenv",
    "streamlit-autorefresh": "streamlit_autorefresh",
    "umap-learn": "umap",
    "google-genai": "google.genai",
    "pyyaml": "yaml",
    "pillow": "PIL",
    "beautifulsoup4": "bs4",
}


def get_base_dir() -> str:
    """Returns the project base directory."""
    return os.path.dirname(os.path.abspath(__file__))


def get_venv_python() -> str | None:
    """Finds project .venv python executable if available."""
    base_dir = get_base_dir()
    if sys.platform == "win32":
        venv_py = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join(base_dir, ".venv", "bin", "python")
    return venv_py if os.path.isfile(venv_py) else None


def get_module_name(package_name: str) -> str:
    """Normalize package name to importable Python module name."""
    clean_name = package_name.strip().split(";")[0].split("#")[0].strip()
    for op in [">=", "<=", "==", "~=", "!=", ">", "<"]:
        if op in clean_name:
            clean_name = clean_name.split(op)[0].strip()
    
    clean_lower = clean_name.lower()
    if clean_lower in PACKAGE_TO_MODULE_MAP:
        return PACKAGE_TO_MODULE_MAP[clean_lower]
    
    return clean_name.replace("-", "_")


def is_module_installed(module_name: str) -> bool:
    """Check if a module is importable in the current environment."""
    try:
        if "." in module_name:
            top_level = module_name.split(".")[0]
            if importlib.util.find_spec(top_level) is None:
                return False
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def get_requirements_filepath() -> str:
    """Find requirements.txt path relative to this script."""
    return os.path.join(get_base_dir(), "requirements.txt")


def parse_requirements(req_file: str = None) -> list[str]:
    """Parse requirement lines from requirements.txt file."""
    if req_file is None:
        req_file = get_requirements_filepath()

    requirements = []
    if os.path.isfile(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    requirements.append(line)
    else:
        requirements = [
            "psutil>=7.0.0",
            "numpy>=1.26.0",
            "pandas>=2.2.0",
            "scikit-learn>=1.4.0",
            "joblib>=1.4.0",
            "xgboost>=2.0.0",
            "sqlalchemy>=2.0.0",
            "google-genai>=2.16.0",
            "groq>=1.6.0",
            "requests>=2.31.0",
            "python-dotenv>=1.0.0",
            "streamlit>=1.35.0",
            "streamlit-autorefresh>=1.0.1",
            "plotly>=5.20.0",
            "matplotlib>=3.8.0",
            "seaborn>=0.13.0",
            "umap-learn>=0.5.5",
        ]
    return requirements


def check_missing_packages(req_file: str = None) -> list[tuple[str, str]]:
    """
    Returns a list of tuples: (raw_requirement_spec, package_name)
    for packages missing in the current Python runtime.
    """
    requirements = parse_requirements(req_file)
    missing = []

    for req in requirements:
        mod_name = get_module_name(req)
        if not is_module_installed(mod_name):
            pkg_name = req.strip().split(";")[0].strip()
            for op in [">=", "<=", "==", "~=", "!=", ">", "<"]:
                if op in pkg_name:
                    pkg_name = pkg_name.split(op)[0].strip()
            missing.append((req, pkg_name))

    return missing


def install_packages(packages: list[str]) -> bool:
    """Gracefully install missing packages using pip with venv/system fallback."""
    if not packages:
        return True

    venv_py = get_venv_python()
    python_bin = venv_py if venv_py else sys.executable

    print(f"\n[CogniOS Dependency Manager] Installing missing package(s): {', '.join(packages)}...")
    print(f"[i] Using Python executable: {python_bin}")

    cmd = [python_bin, "-m", "pip", "install"] + packages

    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode == 0:
            print(f"[✔] Successfully installed: {', '.join(packages)}")
            return True

        # If system python fails due to externally-managed-environment (PEP 668), try with --break-system-packages or user flag
        if "externally-managed-environment" in process.stderr:
            print("[i] Retrying installation with --break-system-packages for system Python...")
            cmd_fallback = [python_bin, "-m", "pip", "install", "--break-system-packages"] + packages
            process_fb = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process_fb.returncode == 0:
                print(f"[✔] Successfully installed: {', '.join(packages)}")
                return True
            else:
                print(f"[!] Fallback pip install error:\n{process_fb.stderr}")
                return False

        print(f"[!] Warning: pip installation failed:\n{process.stderr}")
        return False
    except Exception as e:
        print(f"[!] Error executing pip install: {e}")
        return False


def ensure_requirements(auto_install: bool = True, quiet: bool = False) -> bool:
    """
    Main entry point: Checks dependencies and gracefully installs missing packages.
    """
    req_file = get_requirements_filepath()
    missing_items = check_missing_packages(req_file)

    if not missing_items:
        if not quiet:
            print("[✔] CogniOS Dependency Check: All required modules are installed and available.")
        return True

    missing_pkgs = [pkg for req, pkg in missing_items]
    missing_specs = [req for req, pkg in missing_items]

    if not quiet:
        print("\n" + "=" * 60)
        print("🔍 CogniOS Dependency Checker")
        print("=" * 60)
        print(f"Missing modules detected ({len(missing_pkgs)}): {', '.join(missing_pkgs)}")

    if auto_install:
        if not quiet:
            print("📦 Attempting graceful auto-installation...")
        success = install_packages(missing_specs)
        return success
    else:
        if not quiet:
            print("\nAuto-install disabled. Run manually:")
            print(f"  pip install {' '.join(missing_pkgs)}")
        return False


if __name__ == "__main__":
    print("Executing CogniOS Requirements Checker & Auto-Installer...")
    success = ensure_requirements(auto_install=True, quiet=False)
    if success:
        print("\n🎉 All requirements verified!")
    else:
        print("\n⚠️ Requirements check completed with warnings.")
