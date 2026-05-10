import subprocess
import sys
from pathlib import Path

SCORING_SCRIPTS = [
    "backend/processing/scoring/score_consultations.py",
    "backend/processing/scoring/score_proposals.py",
    "backend/processing/scoring/score_guidelines.py",
    "backend/processing/scoring/score_rts.py",
]


def run_script(script_name):
    script_path = Path(script_name)

    if not script_path.exists():
        print(f"SKIPPED: {script_name} was not found.")
        return

    print(f"Running {script_name}...")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print(result.stdout.strip())

    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed.")


def main():
    for script_name in SCORING_SCRIPTS:
        run_script(script_name)

    print("All available scoring scripts completed.")


if __name__ == "__main__":
    main()
