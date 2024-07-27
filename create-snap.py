import subprocess
import datetime

# Create a log file
log_file = f"snapshot_log_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt"

# Prompt for the CHG number
chg_number = input("Enter the CHG number: ")
with open(log_file, "a") as f:
    f.write(f"{chg_number}\n")

# Define the number of days after which snapshots should be considered expired
expire_days = 3

# Create lists for successful and failed snapshots
successful_snapshots = []
failed_snapshots = []

# Loop through each resource ID in snapshot_vmlist.txt
with open("snapshot_vmlist.txt", "r") as f:
    for line in f:
        resource_id, vm_name = line.strip().split()

        # Print the resource ID
        print(f"Creating snapshot for VM with resource ID: {resource_id}")
        subprocess.run(f"echo 'Creating snapshot for VM with resource ID: {resource_id}' >> {log_file}", shell=True)

        # Get the subscription ID
        subscription_id = resource_id.split("/")[2]
        if not subscription_id:
            print(f"Failed to get subscription ID for VM with resource ID: {resource_id}")
            subprocess.run(f"echo 'Failed to get subscription ID for VM with resource ID: {resource_id}' >> {log_file}", shell=True)
            continue

        # Set the subscription ID
        result = subprocess.run(f"az account set --subscription {subscription_id}", shell=True)
        if result.returncode != 0:
            print(f"Failed to set subscription ID: {subscription_id}")
            subprocess.run(f"echo 'Failed to set subscription ID: {subscription_id}' >> {log_file}", shell=True)
            continue

        # Print the subscription ID
        print(f"Subscription ID: {subscription_id}")
        subprocess.run(f"echo 'Subscription ID: {subscription_id}' >> {log_file}", shell=True)

        # Print the resource group name
        resource_group = subprocess.check_output(f"az vm show --ids {resource_id} --query 'resourceGroup' -o tsv", shell=True).decode().strip()
        print(f"Resource group name: {resource_group}")
        subprocess.run(f"echo 'Resource group name: {resource_group}' >> {log_file}", shell=True)

        # Print the VM name
        print(f"VM name: {vm_name}")
        subprocess.run(f"echo 'VM name: {vm_name}' >> {log_file}", shell=True)

        # Get the disk ID of the VM's OS disk
        disk_id = subprocess.check_output(f"az vm show --ids {resource_id} --query 'storageProfile.osDisk.managedDisk.id' -o tsv", shell=True).decode().strip()
        if not disk_id:
            print(f"Failed to get disk ID for VM with resource ID: {resource_id}")
            subprocess.run(f"echo 'Failed to get disk ID for VM with resource ID: {resource_id}' >> {log_file}", shell=True)
            continue

        # Create a snapshot
        snapshot_name = f"RH_{vm_name}_{chg_number}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = subprocess.run(f"az snapshot create --name {snapshot_name} --resource-group {resource_group} --source {disk_id}", shell=True)
        if result.returncode != 0:
            print(f"Failed to create snapshot for VM with resource ID: {resource_id}")
            subprocess.run(f"echo 'Failed to create snapshot for VM with resource ID: {resource_id}' >> {log_file}", shell=True)
            failed_snapshots.append(f"{resource_id}: Failed to create snapshot")
            continue

        # Check if the snapshot is expired
        snapshot_creation_time = datetime.datetime.strptime(snapshot_name.split("_")[-1], "%Y%m%d%H%M%S")
        if (datetime.datetime.now() - snapshot_creation_time).days > expire_days:
            print(f"Snapshot '{snapshot_name}' is expired, deleting...")
            subprocess.run(f"az snapshot delete --ids {resource_id} --yes", shell=True)
            continue

        # Print a success message
        print(f"Snapshot created successfully for VM with resource ID: {resource_id}")
        subprocess.run(f"echo 'Snapshot created successfully for VM with resource ID: {resource_id}' >> {log_file}", shell=True)
        successful_snapshots.append(snapshot_name)

# Print a completion message
print("Snapshot creation and expiration process completed successfully.")
subprocess.run(f"echo 'Snapshot creation and expiration process completed successfully.' >> {log_file}", shell=True)

# Print the summary
print("Summary:")
subprocess.run(f"echo 'Summary:' >> {log_file}", shell=True)
print("Successful snapshots:")
subprocess.run(f"echo 'Successful snapshots:' >> {log_file}", shell=True)
for snapshot in successful_snapshots:
    print(snapshot)
    subprocess.run(f"echo '{snapshot}' >> {log_file}", shell=True)
print("Failed snapshots:")
subprocess.run(f"echo 'Failed snapshots:' >> {log_file}", shell=True)
for snapshot in failed_snapshots:
    print(snapshot)
    subprocess.run(f"echo '{snapshot}' >> {log_file}", shell=True)