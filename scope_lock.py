import subprocess
import json
from datetime import datetime
import os

# Log files
log_file = "scope_lock_operations.log"
removed_locks_file = "removed_locks.json"

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"{timestamp}: {message}\n")
    print(message)

def log_removed_lock(subscription_id, resource_group, lock_name, lock_type, notes):
    if not os.path.exists(removed_locks_file):
        removed_locks = []
    else:
        with open(removed_locks_file, 'r') as f:
            removed_locks = json.load(f)
    
    removed_locks.append({
        "timestamp": datetime.now().isoformat(),
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "lock_name": lock_name,
        "lock_type": lock_type,
        "notes": notes
    })
    
    with open(removed_locks_file, 'w') as f:
        json.dump(removed_locks, f, indent=2)
    
    log_message(f"Logged removed lock: {lock_name} from resource group {resource_group}")

def run_az_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output.strip()}"

def set_subscription(subscription_id):
    command = f"az account set --subscription {subscription_id}"
    result = run_az_command(command)
    if "Error" not in result:
        log_message(f"Successfully switched to subscription: {subscription_id}")
    else:
        log_message(f"Failed to switch subscription: {result}")
        exit(1)

def remove_scope_lock(subscription_id, resource_group, lock_name="lock"):
    log_message(f"Attempting to remove lock '{lock_name}' from resource group '{resource_group}'")
    
    # List locks
    list_command = f"az lock list --resource-group {resource_group} --output json"
    locks_json = run_az_command(list_command)
    
    if "Error" in locks_json:
        log_message(f"Error listing locks: {locks_json}")
        return False
    
    locks = json.loads(locks_json)
    if not locks:
        log_message(f"No locks found for resource group '{resource_group}'")
        return True
    
    # Find the specific lock
    lock = next((l for l in locks if l['name'] == lock_name), None)
    if not lock:
        log_message(f"Lock '{lock_name}' not found in resource group '{resource_group}'")
        return False
    
    # Remove lock
    delete_command = f"az lock delete --name {lock_name} --resource-group {resource_group} --verbose"
    result = run_az_command(delete_command)
    
    if "Error" not in result:
        log_message(f"Successfully removed lock '{lock_name}' from resource group '{resource_group}'")
        log_removed_lock(subscription_id, resource_group, lock_name, lock['level'], lock.get('notes'))
        return True
    else:
        log_message(f"Failed to remove lock: {result}")
        return False

def restore_scope_lock(resource_group, lock_name, lock_type, notes=None):
    log_message(f"Attempting to restore lock '{lock_name}' on resource group '{resource_group}'")
    
    create_command = f"az lock create --name {lock_name} --resource-group {resource_group} --lock-type {lock_type}"
    if notes:
        create_command += f" --notes '{notes}'"
    
    result = run_az_command(create_command)
    
    if "Error" not in result:
        log_message(f"Successfully restored lock '{lock_name}' on resource group '{resource_group}'")
        return True
    else:
        log_message(f"Failed to restore lock: {result}")
        return False

def main():
    subscription_id = input("Enter the subscription ID (press Enter to use current subscription): ").strip()
    if subscription_id:
        set_subscription(subscription_id)
    else:
        # Get current subscription ID
        subscription_id = run_az_command("az account show --query id --output tsv")
    
    resource_group = input("Enter the resource group name: ").strip()
    lock_name = input("Enter the lock name (default is 'lock'): ").strip() or "lock"
    
    action = input("Do you want to remove or restore a lock? (remove/restore): ").strip().lower()
    
    if action == "remove":
        success = remove_scope_lock(subscription_id, resource_group, lock_name)
        if success:
            print("\nLock removal process completed successfully.")
        else:
            print("\nLock removal process encountered errors. Check the log file for details.")
    elif action == "restore":
        lock_type = input("Enter the lock type (CanNotDelete/ReadOnly): ").strip()
        notes = input("Enter any notes for the lock (optional): ").strip() or None
        success = restore_scope_lock(resource_group, lock_name, lock_type, notes)
        if success:
            print("\nLock restoration process completed successfully.")
        else:
            print("\nLock restoration process encountered errors. Check the log file for details.")
    else:
        print("Invalid action. Please choose 'remove' or 'restore'.")

if __name__ == "__main__":
    main()