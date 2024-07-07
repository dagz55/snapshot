import asyncio
import csv
import logging
import os
import time
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
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
    if not content:
        return []
    lines = content.splitlines()
    # Skip header if present
    if lines and lines[0].lower().startswith("id"):
        lines = lines[1:]
    return [line.split(',')[0].strip() for line in lines if line.strip()]

def read_snapshot_inventory(filename):
    inventory = {}
    content = read_file(filename)
    if not content:
        return inventory
    
    try:
        reader = csv.reader(content.splitlines())
        next(reader)  # Skip header
        for row in reader:
            if len(row) >= 1:
                full_path = row[0]
                snapshot_name = full_path.split('/')[-1]
                inventory[snapshot_name] = full_path
                inventory[full_path] = full_path  # Allow lookup by full path as well
    except Exception as e:
        logging.error(f"Error parsing snapshot inventory: {e}")
        console.print(f"[bold red]Error parsing snapshot inventory: {e}[/bold red]")
    
    return inventory

async def check_resource_group_lock(resource_group, max_retries=3):
    lock_name = f"{resource_group.lower()}-lock"
    for attempt in range(max_retries):
        try:
            check_lock_cmd = f"az lock list --resource-group {resource_group} --query '[].name' -o tsv"
            stdout, stderr = await run_command(check_lock_cmd)
            if stderr:
                logging.warning(f"Error checking locks for resource group {resource_group}: {stderr}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return bool(stdout)
        except Exception as e:
            logging.error(f"Exception occurred while checking locks for {resource_group}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                return False  # Assume unlocked if all retries fail
    return False  # Assume unlocked if all retries fail

async def remove_resource_group_lock(resource_group):
    remove_lock_cmd = f"az lock delete --resource-group {resource_group} --ids $(az lock list --resource-group {resource_group} --query '[].id' -o tsv)"
    stdout, stderr = await run_command(remove_lock_cmd)
    if stderr:
        logging.error(f"Failed to remove locks from resource group {resource_group}: {stderr}")
        return False
    logging.info(f"Successfully removed locks from resource group {resource_group}")
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
    not_found_count = 0
    locks_removed = set()
    total_count = len(snapshot_names)

    # Group snapshots by resource group
    snapshots_by_group = {}
    for snapshot_id in snapshot_names:
        full_path = snapshot_inventory.get(snapshot_id, snapshot_id)
        parts = full_path.split('/')
        if len(parts) < 5:
            logging.warning(f"Invalid snapshot ID format: {snapshot_id}")
            not_found_count += 1
            progress.update(task_id, advance=1)
            continue
        resource_group = parts[4]
        if resource_group not in snapshots_by_group:
            snapshots_by_group[resource_group] = []
        snapshots_by_group[resource_group].append(full_path)

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
                    progress.update(task_id, advance=len(snapshots))
                    continue
            else:
                logging.info(f"Skipping all snapshots in {resource_group} due to lock")
                skipped_count += len(snapshots)
                progress.update(task_id, advance=len(snapshots))
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
                console.print(f"Deleted: {deleted_count}, Skipped: {skipped_count}, Not Found: {not_found_count}, Remaining: {total_count - deleted_count - skipped_count - not_found_count}", end="\r")

    # Restore locks
    for resource_group in locks_removed:
        await restore_resource_group_lock(resource_group)

    return deleted_count, skipped_count, not_found_count

async def main():
    console.print(Panel.fit(
        Text("Azure Snapshot Management Tool", style="bold magenta"),
        border_style="cyan"
    ))

    snapshot_list_file = Prompt.ask("Enter the path to the snapshot list file", default="snap_list")
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

    start_time = time.time()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing snapshots...", total=len(snapshot_names))
        
        deleted_count, skipped_count, not_found_count = await process_snapshots(snapshot_inventory, snapshot_names, progress, task, force_delete)

        # Ensure progress reaches 100%
        progress.update(task, completed=len(snapshot_names))

    end_time = time.time()
    duration = end_time - start_time

    console.print(f"\n[bold blue]Script runtime: {duration:.2f} seconds[/bold blue]")
    console.print(f"[bold green]Total snapshots deleted: {deleted_count}[/bold green]")
    console.print(f"[bold yellow]Total snapshots skipped: {skipped_count}[/bold yellow]")
    console.print(f"[bold red]Total snapshots not found: {not_found_count}[/bold red]")
    console.print(f"[bold cyan]Total remaining: {len(snapshot_names) - deleted_count - skipped_count - not_found_count}[/bold cyan]")
    
    logging.info(f"Completed deletion. Total snapshots deleted: {deleted_count}, Total snapshots skipped: {skipped_count}, Not found: {not_found_count}, Remaining: {len(snapshot_names) - deleted_count - skipped_count - not_found_count}")
    logging.info(f"Script runtime: {duration:.2f} seconds")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(Panel(f"An unexpected error occurred: {str(e)}", border_style="red"))
        logging.error(f"Unexpected error: {str(e)}")
