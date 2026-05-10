"""
Processing Orchestrator
Handles scoring, categorization, and summarization of regulatory documents
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

PROCESSING_STAGES = [
    {
        "name": "Summarization",
        "module": "backend.processing.summaries.create_summaries",
    },
    {
        "name": "Categorization",
        "module": "backend.processing.categorization.main",
    },
    {
        "name": "Scoring",
        "module": "backend.processing.scoring.main",
    }
]


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_stage(stage_name, module_path):
    print(f"\nRunning {stage_name}...")

    result = subprocess.run(
        [sys.executable, "-m", module_path],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print(result.stdout.strip())

    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0:
        print(f"⚠ {stage_name} failed with return code {result.returncode}")
        return False

    return True


def main():
    start_time = datetime.now()
    
    print_header("EU REGULATORY DATA PROCESSING SYSTEM")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    completed_stages = []
    failed_stages = []
    
    for stage in PROCESSING_STAGES:
        success = run_stage(stage["name"], stage["module"])
        
        if success:
            completed_stages.append(stage["name"])
        else:
            failed_stages.append(stage["name"])
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("PROCESSING COMPLETE")
    print(f"Completed stages: {', '.join(completed_stages) if completed_stages else 'None'}")
    if failed_stages:
        print(f"Failed stages: {', '.join(failed_stages)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
