import os
import subprocess
from tqdm import tqdm

# Log files
deleted_log = "deleted_snap.log"
error_log = "error_snap.log"
not_found_log = "not_found_snap.log"

def delete_snapshots(batch):
    global deleted_count
    try:
        subprocess.check_output(f'az snapshot delete --ids {batch}', stderr=subprocess.STDOUT, shell=True)
        for snapshot_id in batch.split(','):
            with open(deleted_log, 'a') as f:
                f.write(f"{snapshot_id}\n")
            deleted_count += 1
        print(f"\033[92mChecked: {deleted_count}\033[0m")
    except subprocess.CalledProcessError as e:
        with open(error_log, 'a') as f:
            f.write(str(e.output))
        print("\033[91mError deleting snapshots.\033[0m")

def main():
    global deleted_count
    deleted_count = 0
    not_found_count = 0
    filename = input("Enter the filename: ")
    if not os.path.isfile(filename):
        print(f"File {filename} does not exist.")
        return
    with open(filename, 'r') as f:
        snapshot_ids = f.read().splitlines()
    existing_snapshots = []
    non_existing_snapshots = []
    for snapshot_id in tqdm(snapshot_ids, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'):
        try:
            subprocess.check_output(f'az snapshot show --ids {snapshot_id}', stderr=subprocess.STDOUT, shell=True)
            existing_snapshots.append(snapshot_id)
        except subprocess.CalledProcessError:
            non_existing_snapshots.append(snapshot_id)
            with open(not_found_log, 'a') as f:
                f.write(f"{snapshot_id}\n")
            not_found_count += 1
    print(f"\n\033[93mSnapshots not found: {not_found_count}\033[0m")
    print("\033[93mSee not_found_snap.log for details.\033[0m")
    batch_size = 10
    while existing_snapshots:
        batch = ','.join(existing_snapshots[:batch_size])
        delete_snapshots(batch)
        existing_snapshots = existing_snapshots[batch_size:]
    print("Deletion completed. Log files generated:")
    print(f"- Deleted snapshots: {deleted_log}")
    print(f"- Error snapshots: {error_log}")
    print(f"- Not found snapshots: {not_found_log}")

if __name__ == "__main__":
    main()