import subprocess
import sys
from pathlib import Path

CATEGORY_SCRIPTS = [
    "backend/processing/categorization/refine_categories.py",
    "backend/processing/categorization/ai_categories.py",
    "backend/processing/categorization/combined_categories.py",
]


def run_script(script_name):
    script_path = Path(script_name)

    if not script_path.exists():
        raise FileNotFoundError(f"{script_name} was not found.")

    print(f"Running {script_name}...")

    result = subprocess.run(
        [sys.executable, script_name],
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed.")

    print(f"Finished {script_name}.\n")


def main():
    for script_name in CATEGORY_SCRIPTS:
        run_script(script_name)

    print("All category scripts completed successfully.")


if __name__ == "__main__":
    main()
