import os
import subprocess
import time
from datetime import datetime
from halo import Halo

# Log files
not_found_log = "not_found_snap.log"
found_log = "found_snap.log"

def log_message(log_file, message):
    with open(log_file, 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

def check_snapshots(snapshot_ids):
    not_found_count = 0
    found_count = 0

    spinner = Halo(text='Validating snapshots...', spinner='arrow3')
    spinner.start()

    total_snapshots = len(snapshot_ids)
    for i, snapshot_id in enumerate(snapshot_ids, start=1):
        try:
            subprocess.check_output(f'az snapshot show --ids {snapshot_id}', stderr=subprocess.STDOUT, shell=True)
            log_message(found_log, f"Snapshot found: {snapshot_id}")
            found_count += 1
        except subprocess.CalledProcessError:
            log_message(not_found_log, f"Snapshot not found: {snapshot_id}")
            not_found_count += 1

        # Update spinner text with progress
        spinner.text = f'Validating snapshots... ({i}/{total_snapshots})'

    spinner.stop()

    return found_count, not_found_count

def main():
    filename = input("Enter the filename: ")
    if not os.path.isfile(filename):
        print(f"File {filename} does not exist.")
        return

    start_time = time.time()

    try:
        with open(filename, 'r') as f:
            snapshot_ids = f.read().splitlines()
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        return

    found_count, not_found_count = check_snapshots(snapshot_ids)

    end_time = time.time()
    total_runtime = end_time - start_time

    print(f"\n\033[92mSnapshots found: {found_count}\033[0m")
    print(f"\033[93mSnapshots not found: {not_found_count}\033[0m")
    print(f"\033[4m\033[93mSee {not_found_log} for details.\033[0m")
    print(f"\033[4m\033[92mSee {found_log} for details.\033[0m")
    print(f"\n\033[94mTotal runtime: {total_runtime:.2f} seconds\033[0m")

if __name__ == "__main__":
    main()
