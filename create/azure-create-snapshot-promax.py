import subprocess
import datetime
import json
from rich.console import Console
from rich.progress import Progress

# Create log files
timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
log_file = f"snapshot_log_{timestamp}.txt"
summary_file = f"snapshot_summary_{timestamp}.txt"

# Create a Console object
console = Console()

# Prompt for the CHG number
chg_number = input("Enter the CHG number: ")
with open(log_file, "a") as f:
    f.write(f"CHG Number: {chg_number}\n\n")

# Define the number of days after which snapshots should be considered expired
expire_days = 3

# Create lists for successful and failed snapshots
successful_snapshots = []
failed_snapshots = []

# Get the total number of VMs to process
with open("snapshot_vmlist.txt", "r") as file:
    total_vms = len(file.readlines())

# Function to write detailed logs
def write_detailed_log(message):
    with open(log_file, "a") as f:
        f.write(f"{message}\n")

# Loop through each resource ID in snapshot_vmlist.txt
with open("snapshot_vmlist.txt", "r") as file:
    with Progress() as progress:
        task = progress.add_task("[cyan]Processing VMs...", total=total_vms)
        for line in file:
            resource_id, vm_name = line.strip().split()

            write_detailed_log(f"Processing VM: {vm_name}")
            write_detailed_log(f"Resource ID: {resource_id}")

            # Get the subscription ID
            subscription_id = resource_id.split("/")[2]
            if not subscription_id:
                console.print(f"Failed to get subscription ID for VM: {vm_name}")
                write_detailed_log(f"Failed to get subscription ID for VM: {vm_name}")
                failed_snapshots.append(f"{vm_name}: Failed to get subscription ID")
                continue

            # Set the subscription ID
            result = subprocess.run(f"az account set --subscription {subscription_id}", shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                console.print(f"Failed to set subscription ID for VM: {vm_name}")
                write_detailed_log(f"Failed to set subscription ID: {subscription_id}")
                write_detailed_log(f"Error: {result.stderr}")
                failed_snapshots.append(f"{vm_name}: Failed to set subscription ID")
                continue

            write_detailed_log(f"Subscription ID: {subscription_id}")

            # Get the resource group name
            resource_group = subprocess.check_output(f"az vm show --ids {resource_id} --query 'resourceGroup' -o tsv", shell=True).decode().strip()
            write_detailed_log(f"Resource group name: {resource_group}")

            # Get the disk ID of the VM's OS disk
            disk_id = subprocess.check_output(f"az vm show --ids {resource_id} --query 'storageProfile.osDisk.managedDisk.id' -o tsv", shell=True).decode().strip()
            if not disk_id:
                console.print(f"Failed to get disk ID for VM: {vm_name}")
                write_detailed_log(f"Failed to get disk ID for VM: {vm_name}")
                failed_snapshots.append(f"{vm_name}: Failed to get disk ID")
                continue

            # Create a snapshot
            snapshot_name = f"RH_{vm_name}_{chg_number}_{timestamp}"
            result = subprocess.run(f"az snapshot create --name {snapshot_name} --resource-group {resource_group} --source {disk_id}", shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                console.print(f"Failed to create snapshot for VM: {vm_name}")
                write_detailed_log(f"Failed to create snapshot for VM: {vm_name}")
                write_detailed_log(f"Error: {result.stderr}")
                failed_snapshots.append(f"{vm_name}: Failed to create snapshot")
                continue

            # Write snapshot details to log file
            write_detailed_log(f"Snapshot created: {snapshot_name}")
            write_detailed_log(json.dumps(json.loads(result.stdout), indent=2))

            # Check if the snapshot is expired
            snapshot_creation_time = datetime.datetime.strptime(snapshot_name.split("_")[-1], "%Y%m%d%H%M%S")
            if (datetime.datetime.now() - snapshot_creation_time).days > expire_days:
                console.print(f"Snapshot '{snapshot_name}' is expired, deleting...")
                subprocess.run(f"az snapshot delete --name {snapshot_name} --resource-group {resource_group} --yes", shell=True)
                write_detailed_log(f"Deleted expired snapshot: {snapshot_name}")
                continue

            console.print(f"Snapshot created successfully for VM: {vm_name}")
            successful_snapshots.append(snapshot_name)

            # Update the progress bar
            progress.update(task, advance=1)

# Write summary to file
with open(summary_file, "w") as f:
    f.write("Snapshot Creation Summary\n")
    f.write("========================\n\n")
    f.write(f"Total VMs processed: {total_vms}\n")
    f.write(f"Successful snapshots: {len(successful_snapshots)}\n")
    f.write(f"Failed snapshots: {len(failed_snapshots)}\n\n")
    
    f.write("Successful snapshots:\n")
    for snapshot in successful_snapshots:
        f.write(f"- {snapshot}\n")
    
    f.write("\nFailed snapshots:\n")
    for snapshot in failed_snapshots:
        f.write(f"- {snapshot}\n")

# Print completion message and summary location
console.print("\nSnapshot creation and expiration process completed.")
console.print(f"Detailed log: {log_file}")
console.print(f"Summary: {summary_file}")
