"""
Top-level orchestrator for EU Regulatory Data Collection and Processing System
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

MAIN_STAGES = [
    {
        "name": "Data Collection",
        "module": "backend.data_collection.main",
    },
    {
        "name": "Data Processing",
        "module": "backend.processing.main",
    },
]


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_stage(stage_name, module_path):
    print(f"\n>>> {stage_name}...")

    result = subprocess.run([sys.executable, "-m", module_path])
    return result.returncode == 0


def main():
    start_time = datetime.now()
    
    print_header("EU REGULATORY DATA SYSTEM")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    completed = []
    failed = []
    
    for stage in MAIN_STAGES:
        success = run_stage(stage["name"], stage["module"])
        if success:
            completed.append(stage["name"])
        else:
            failed.append(stage["name"])
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("SYSTEM EXECUTION COMPLETE")
    print(f"Completed: {', '.join(completed) if completed else 'None'}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
