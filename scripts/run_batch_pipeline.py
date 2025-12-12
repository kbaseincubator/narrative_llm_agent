#!/usr/bin/env python3
"""
Batch process UPAs through full_pipeline.py
Maintains a continuous pool of 10 running processes.
"""

import subprocess
import sys
import os
from pathlib import Path

# Configuration
POOL_SIZE = 10
READS_UPA_FILE = Path(__file__).parent / ".." / "reads_upas.txt"
FULL_PIPELINE_SCRIPT = Path(__file__).parent / "full_pipeline.py"

def read_upas(file_path):
    """Read UPAs from file, filtering out empty lines and comments."""
    upas = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Extract the UPA part (after the arrow if present)
            if '→' in line:
                upa = line.split('→')[-1].strip()
            else:
                upa = line

            if upa and not upa.startswith('#'):
                upas.append(upa)
    return upas

def get_command(upa):
    """Build the full_pipeline.py command for a given UPA."""
    # Ensure environment variables are set
    kb_auth_token = os.environ.get('KB_AUTH_TOKEN', '')
    cborg_api_key = os.environ.get('CBORG_KBASE_API_KEY', '')

    if not kb_auth_token:
        print("Warning: KB_AUTH_TOKEN not set in environment")
    if not cborg_api_key:
        print("Warning: CBORG_KBASE_API_KEY not set in environment")

    cmd = [
        sys.executable,
        str(FULL_PIPELINE_SCRIPT),
        '-k', kb_auth_token,
        '-p', 'cborg',
        '-l', cborg_api_key,
        '-t', 'pe_reads_interleaved',
        '-u', upa
    ]
    return cmd

def run_all_upas(upas):
    """Run all UPAs while maintaining a pool of POOL_SIZE processes."""
    active_processes = []  # List of (upa, process, log_file)
    upa_index = 0
    completed = 0
    failed = []
    total = len(upas)

    # Start initial pool
    print(f"Starting pool of {POOL_SIZE} processes...")
    while upa_index < min(POOL_SIZE, total):
        upa = upas[upa_index]
        cmd = get_command(upa)
        print(f"  Launching [{upa_index + 1}/{total}]: {upa}")

        try:
            log_file = open(f"pipeline_batch_{upa.replace('/', '_')}.log", 'w')
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True
            )
            active_processes.append((upa, process, log_file))
        except Exception as e:
            print(f"  Error launching process for {upa}: {e}")
            failed.append((upa, -1))

        upa_index += 1

    # Continuously monitor and replace completed processes
    print(f"\nMonitoring {len(active_processes)} active processes...")
    while active_processes:
        # Check which processes have completed
        still_running = []
        for upa, process, log_file in active_processes:
            return_code = process.poll()

            if return_code is not None:
                # Process completed
                log_file.close()
                completed += 1

                if return_code == 0:
                    print(f"  ✓ Completed [{completed}/{total}]: {upa}")
                else:
                    print(f"  ✗ Failed [{completed}/{total}]: {upa} (exit code: {return_code})")
                    failed.append((upa, return_code))

                # Start a new process if there are more UPAs
                if upa_index < total:
                    new_upa = upas[upa_index]
                    cmd = get_command(new_upa)
                    print(f"  Launching [{upa_index + 1}/{total}]: {new_upa}")

                    try:
                        log_file = open(f"pipeline_batch_{new_upa.replace('/', '_')}.log", 'w')
                        process = subprocess.Popen(
                            cmd,
                            stdout=log_file,
                            stderr=subprocess.STDOUT,
                            text=True
                        )
                        still_running.append((new_upa, process, log_file))
                    except Exception as e:
                        print(f"  Error launching process for {new_upa}: {e}")
                        failed.append((new_upa, -1))

                    upa_index += 1
            else:
                # Process still running
                still_running.append((upa, process, log_file))

        active_processes = still_running

        # Avoid busy waiting
        if active_processes:
            import time
            time.sleep(0.5)

    return failed

def main():
    if not FULL_PIPELINE_SCRIPT.exists():
        print(f"Error: full_pipeline.py not found at {FULL_PIPELINE_SCRIPT}")
        sys.exit(1)

    if not READS_UPA_FILE.exists():
        print(f"Error: reads_upas.txt not found at {READS_UPA_FILE}")
        sys.exit(1)

    # Read all UPAs
    upas = read_upas(READS_UPA_FILE)
    print(f"Loaded {len(upas)} UPAs from {READS_UPA_FILE}")
    print(f"Pool size: {POOL_SIZE}")

    print(f"\n{'='*60}")
    print("PROCESSING")
    print(f"{'='*60}\n")

    # Process all UPAs with continuous pool
    all_failed = run_all_upas(upas)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total UPAs processed: {len(upas)}")
    print(f"Successful: {len(upas) - len(all_failed)}")
    print(f"Failed: {len(all_failed)}")

    if all_failed:
        print("\nFailed UPAs:")
        for upa, return_code in all_failed:
            print(f"  - {upa} (exit code: {return_code})")
        sys.exit(1)
    else:
        print("\nAll UPAs completed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
