import asyncio
import csv
import logging
import os
import time
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.text import Text

# Configure logging
logging.basicConfig(filename='snapshot_management.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

console = Console()

async def run_command(cmd):
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode().strip(), stderr.decode().strip()

def read_file(filename):
    if not os.path.exists(filename):
        logging.error(f"File not found: {filename}")
        console.print(f"[bold red]File not found: {filename}[/bold red]")
        return None
    try:
        with open(filename, 'r') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading file {filename}: {e}")
        console.print(f"[bold red]Error reading file {filename}: {e}[/bold red]")
        return None

def read_snapshot_list(filename):
    content = read_file(filename)
    return [line.strip() for line in content.splitlines() if line.strip()] if content else []

def read_snapshot_inventory(filename):
    inventory = {}
    content = read_file(filename)
    if not content:
        return inventory
    
    try:
        reader = csv.reader(content.splitlines())
        next(reader)  # Skip header
        for row in reader:
            if len(row) >= 3:
                full_path = row[0]
                snapshot_name = full_path.split('/')[-1]
                inventory[snapshot_name] = full_path
    except Exception as e:
        logging.error(f"Error parsing snapshot inventory: {e}")
        console.print(f"[bold red]Error parsing snapshot inventory: {e}[/bold red]")
    
    return inventory

async def check_resource_group_lock(resource_group, max_retries=3):
    lock_name = f"{resource_group.lower()}-lock"
    for attempt in range(max_retries):
        try:
            check_lock_cmd = f"az lock show --name {lock_name} --resource-group {resource_group} --query 'name' -o tsv"
            stdout, stderr = await run_command(check_lock_cmd)
            if stderr:
                logging.warning(f"Error checking lock for resource group {resource_group}: {stderr}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return bool(stdout)
        except Exception as e:
            logging.error(f"Exception occurred while checking lock for {resource_group}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                return True  # Assume locked if all retries fail
    return True  # Assume locked if all retries fail

async def remove_resource_group_lock(resource_group):
    lock_name = f"{resource_group.lower()}-lock"
    remove_lock_cmd = f"az lock delete --name {lock_name} --resource-group {resource_group}"
    stdout, stderr = await run_command(remove_lock_cmd)
    if stderr:
        logging.error(f"Failed to remove lock {lock_name} from resource group {resource_group}: {stderr}")
        return False
    logging.info(f"Successfully removed lock {lock_name} from resource group {resource_group}")
    return True

async def restore_resource_group_lock(resource_group, lock_type="CanNotDelete"):
    lock_name = f"{resource_group.lower()}-lock"
    create_lock_cmd = f"az lock create --name {lock_name} --resource-group {resource_group} --lock-type {lock_type}"
    stdout, stderr = await run_command(create_lock_cmd)
    if stderr:
        logging.error(f"Failed to restore lock {lock_name} on resource group {resource_group}: {stderr}")
        return False
    logging.info(f"Successfully restored lock {lock_name} on resource group {resource_group}")
    return True

async def delete_snapshot(snapshot_id):
    try:
        delete_command = f"az resource delete --ids '{snapshot_id}' --verbose"
        stdout, stderr = await run_command(delete_command)
        if stderr and "ERROR:" in stderr:
            logging.error(f"Error deleting snapshot {snapshot_id}: {stderr}")
            console.print(f"[bold red]Error deleting snapshot {snapshot_id}: {stderr}[/bold red]")
            return False
        else:
            logging.info(f"Successfully deleted snapshot {snapshot_id}")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while deleting snapshot {snapshot_id}: {e}")
        console.print(f"[bold red]Exception occurred while deleting snapshot {snapshot_id}: {e}[/bold red]")
        return False

async def process_snapshots(snapshot_inventory, snapshot_names, progress, task_id, force_delete):
    deleted_count = 0
    skipped_count = 0
    resource_group_status = {}
    locks_removed = set()

    # Group snapshots by resource group
    snapshots_by_group = {}
    for snapshot_id in snapshot_names:
        if snapshot_id.startswith('/subscriptions/'):
            parts = snapshot_id.split('/')
            if len(parts) < 5:
                logging.warning(f"Invalid snapshot ID format: {snapshot_id}")
                skipped_count += 1
                continue
            resource_group = parts[4]
        else:
            snapshot_id = snapshot_inventory.get(snapshot_id)
            if not snapshot_id:
                logging.warning(f"Snapshot {snapshot_id} not found in inventory")
                console.print(f"[bold yellow]Warning: Snapshot {snapshot_id} not found in inventory[/bold yellow]")
                skipped_count += 1
                continue
            parts = snapshot_id.split('/')
            resource_group = parts[4]
        
        if resource_group not in snapshots_by_group:
            snapshots_by_group[resource_group] = []
        snapshots_by_group[resource_group].append(snapshot_id)

    # Process snapshots by resource group
    for resource_group, snapshots in snapshots_by_group.items():
        # Check resource group lock
        is_locked = await check_resource_group_lock(resource_group)
        
        if is_locked:
            if force_delete:
                if await remove_resource_group_lock(resource_group):
                    locks_removed.add(resource_group)
                else:
                    logging.warning(f"Skipping all snapshots in {resource_group} due to failure to remove lock")
                    skipped_count += len(snapshots)
                    continue
            else:
                logging.info(f"Skipping all snapshots in {resource_group} due to lock")
                skipped_count += len(snapshots)
                continue

        # Process snapshots in the unlocked group
        for snapshot_id in snapshots:
            try:
                if await delete_snapshot(snapshot_id):
                    deleted_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing snapshot {snapshot_id}: {e}")
                console.print(f"[bold red]Error processing snapshot {snapshot_id}: {e}[/bold red]")
                skipped_count += 1
            finally:
                progress.update(task_id, advance=1)

    # Restore locks
    for resource_group in locks_removed:
        await restore_resource_group_lock(resource_group)

    return deleted_count, skipped_count

async def main():
    console.print(Panel.fit(
        Text("Azure Snapshot Management Tool", style="bold magenta"),
        border_style="cyan"
    ))

    snapshot_list_file = Prompt.ask("Enter the path to the snapshot list file", default="default: snap_list - press enter to accept")
    snapshot_inventory_file = Prompt.ask("Enter the path to the snapshot inventory CSV file", default="snapshots_inventory.csv")
    force_delete = Confirm.ask("Do you want to force delete snapshots even if resource group is locked?", default=False)
    
    snapshot_names = read_snapshot_list(snapshot_list_file)
    snapshot_inventory = read_snapshot_inventory(snapshot_inventory_file)

    if not snapshot_names:
        console.print(Panel("No valid snapshots found in the list. Exiting.", border_style="yellow"))
        return

    if not snapshot_inventory:
        console.print(Panel("No valid snapshot inventory loaded. Proceeding with caution.", border_style="yellow"))

    console.print(Panel(f"Found [bold]{len(snapshot_names)}[/bold] snapshots in the list", border_style="green"))
    console.print(Panel(f"Loaded [bold]{len(snapshot_inventory)}[/bold] snapshots from inventory", border_style="green"))

    logging.info(f"Processing {len(snapshot_names)} snapshots for deletion")
    logging.info(f"Force delete option: {force_delete}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("[cyan]Processing snapshots...", total=len(snapshot_names))
        
        deleted_count, skipped_count = await process_snapshots(snapshot_inventory, snapshot_names, progress, main_task, force_delete)

    console.print(Panel(f"Total snapshots deleted: {deleted_count}\nTotal snapshots skipped: {skipped_count}", border_style="green"))
    logging.info(f"Completed deletion. Total snapshots deleted: {deleted_count}, Total snapshots skipped: {skipped_count}")

if __name__ == "__main__":
    try:
        start_time = time.time()
        asyncio.run(main())
    except Exception as e:
        console.print(Panel(f"An unexpected error occurred: {str(e)}", border_style="red"))
        logging.error(f"Unexpected error: {str(e)}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        console.print(Panel(f"Script runtime: {duration:.2f} seconds", border_style="blue"))
        logging.info(f"Script runtime: {duration:.2f} seconds")
