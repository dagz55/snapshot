import subprocess
import json
import time
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='snapshot_cleanup.log', filemode='a')

# Prompt user for input
RESOURCE_GROUP = input("Enter the Azure resource group name: ")
DEV_RETENTION = input("Enter the retention period for dev snapshots (e.g., '3d'): ")
PROD_RETENTION = input("Enter the retention period for prod snapshots (e.g., '7d'): ")

def get_snapshots(retention):
    try:
        az_command = f"az snapshot list --resource-group {RESOURCE_GROUP} --query \"[?creationData.timeBeforeCurrent < '{retention}'].{{Name:name, Age:creationData.timeBeforeCurrent}}\" -o json"
        result = subprocess.run(az_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Error getting snapshots: {result.stderr}")
            return []
        return json.loads(result.stdout)
    except Exception as e:
        logging.error(f"Exception occurred while getting snapshots: {e}")
        return []

def delete_snapshot(name):
    try:
        delete_command = f"az snapshot delete --resource-group {RESOURCE_GROUP} --name {name} --yes"
        result = subprocess.run(delete_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Error deleting snapshot {name}: {result.stderr}")
        else:
            logging.info(f"Successfully deleted snapshot {name}")
    except Exception as e:
        logging.error(f"Exception occurred while deleting snapshot {name}: {e}")

start_time = time.time()

logging.info("Script started")

dev_snapshots = get_snapshots(DEV_RETENTION)
prod_snapshots = get_snapshots(PROD_RETENTION)

all_snapshots = dev_snapshots + prod_snapshots
total_snapshots = len(all_snapshots)

if not all_snapshots:
    message = f"No snapshots older than {DEV_RETENTION} (dev) or {PROD_RETENTION} (prod) found in resource group {RESOURCE_GROUP}."
    print(message)
    logging.info(message)
else:
    message = f"Snapshots to be deleted in resource group {RESOURCE_GROUP}:"
    print(message)
    logging.info(message)
    
    for snapshot in tqdm(all_snapshots, desc="Processing snapshots", unit="snapshot"):
        name = snapshot['Name']
        if name.startswith(('dgm', 'qgm')) and snapshot in dev_snapshots:
            message = f"Deleting dev snapshot: {name}, Age: {snapshot['Age']}"
            print(message)
            logging.info(message)
            delete_snapshot(name)
        elif name.startswith('pgm') and snapshot in prod_snapshots:
            message = f"Deleting prod snapshot: {name}, Age: {snapshot['Age']}"
            print(message)
            logging.info(message)
            delete_snapshot(name)
    
    message = f"\nTotal number of deleted snapshots: {total_snapshots}"
    print(message)
    logging.info(message)

end_time = time.time()
duration = end_time - start_time
message = f"\nScript runtime: {duration:.2f} seconds"
print(message)
logging.info(message)
