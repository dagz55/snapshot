import subprocess
from tqdm import tqdm
import logging
import os  # Make sure to import os for os.popen and os.system

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Function to delete snapshot
def delete_snapshot(resource_id):
    try:
        subprocess.run(["az", "snapshot", "delete", "--ids", resource_id], check=True)
        return True
    except subprocess.CalledProcessError:
        return False
    
def delete_scope_lock(resource_group_name):
    """
    Deletes the 'CanNotDelete' scope lock from the specified resource group.

    Args:
        resource_group_name (str): The name of the resource group.

    Returns:
        tuple: A tuple containing a boolean indicating the success status and a string message.
    """
    try:
        lock_name = subprocess.run(
            ["az", "lock", "list", "--resource-group", resource_group_name, "--query", "[?level=='CanNotDelete'].name", "-o", "tsv"],
            capture_output=True, text=True, check=True
        ).stdout.strip()

        if lock_name:
            subprocess.run(["az", "lock", "delete", "--name", lock_name, "--resource-group", resource_group_name], check=True)
            logging.info(f"Deleted scope lock '{lock_name}' from resource group '{resource_group_name}'")
            return True, f"Scope lock '{lock_name}' deleted from resource group '{resource_group_name}'"
        else:
            logging.info(f"No scope lock found for resource group '{resource_group_name}'")
            return False, f"No scope lock found for resource group '{resource_group_name}'"
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to delete scope lock from resource group '{resource_group_name}'. Error: {e}")
        return False, str(e)

# Main function
def main():
    # Prompt user for the path to the snapshot list file
    snapshot_list_file = input("Enter the path to the snapshot list file: ")

    # Load snapshot IDs from the file
    try:
        with open(snapshot_list_file, 'r') as file:
            snapshot_ids = file.read().splitlines()
    except FileNotFoundError:
        logging.error(f"File not found: {snapshot_list_file}")
        return

    # Delete snapshots
    results = []
    failed_snapshots = []
    for resource_id in tqdm(snapshot_ids, desc="Deleting snapshots"):
        result = delete_snapshot(resource_id)
        results.append(result)
        if not result:
            failed_snapshots.append(resource_id)

    successful_count = results.count(True)
    failed_count = results.count(False)

    # Log summary
    logging.info("Deletion Summary:")
    logging.info(f"Total Snapshots: {len(snapshot_ids)}")
    logging.info(f"Successfully Deleted: {successful_count}")
    logging.info(f"Failed to Delete: {failed_count}")

    # Process failed snapshots to delete scope locks
    if failed_snapshots:
        logging.info("Processing failed snapshots to delete scope locks...")
        # Assuming the RG ID can be extracted directly from the snapshot RID
        # This extraction logic might need to be adjusted based on your RID format
        failed_rgs = set([rid.split('/')[4] for rid in failed_snapshots])  # Extract RG ID from RID
        for rg in failed_rgs:
            delete_scope_lock(rg)

if __name__ == "__main__":
    main()