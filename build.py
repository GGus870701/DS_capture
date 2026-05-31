import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from build_core.builder import build

def main():
    build(
        app_name           = "DS_Capture",
        main_script        = "main.py",
        version_file       = "core/version.py",
        collect_submodules = ["core", "ui", "modules", "PIL"],
    )

if __name__ == "__main__":
    main()
