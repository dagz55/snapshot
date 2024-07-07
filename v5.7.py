import asyncio
import json
import time
import logging
import csv
from collections import defaultdict
from rich import print
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
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

def read_snapshot_list(filename):
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading snapshot list file: {e}")
        console.print(f"[bold red]Error reading snapshot list file: {e}[/bold red]")
        return []

def read_snapshot_inventory(filename):
    inventory = {}
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 3:
                    full_path = row[0]
                    snapshot_name = full_path.split('/')[-1]
                    inventory[snapshot_name] = full_path
    except Exception as e:
        logging.error(f"Error reading snapshot inventory file: {e}")
        console.print(f"[bold red]Error reading snapshot inventory file: {e}[/bold red]")
    return inventory

async def remove_resource_group_lock(resource_group):
    lock_name = f"{resource_group.lower()}-lock"
    remove_lock_cmd = f"az lock delete --name {lock_name} --resource-group {resource_group}"
    
    for attempt in range(2):  # Try twice
        stdout, stderr = await run_command(remove_lock_cmd)
        if not stderr:
            logging.info(f"Successfully removed lock {lock_name} from resource group {resource_group}")
            return True
        else:
            logging.warning(f"Attempt {attempt + 1} failed to remove lock {lock_name} from resource group {resource_group}: {stderr}")
    
    return False

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

async def process_snapshots(snapshot_inventory, snapshot_names, progress, task_id):
    deleted_count = 0
    skipped_count = 0
    resource_group_status = defaultdict(bool)  # True if processed successfully, False if skipped due to locks

    for i, name in enumerate(snapshot_names):
        try:
            snapshot_id = snapshot_inventory.get(name)
            if snapshot_id:
                resource_group = snapshot_id.split('/')[4]  # Extract resource group from snapshot ID

                if resource_group_status[resource_group] is False:
                    logging.info(f"Skipping snapshot {name} due to previous lock issues in resource group {resource_group}")
                    skipped_count += 1
                    continue

                if resource_group_status[resource_group] is not True:  # If we haven't processed this resource group yet
                    if not await remove_resource_group_lock(resource_group):
                        resource_group_status[resource_group] = False
                        logging.warning(f"Failed to remove lock for resource group {resource_group}. Skipping all snapshots in this group.")
                        skipped_count += 1
                        continue

                    resource_group_status[resource_group] = True

                if await delete_snapshot(snapshot_id):
                    deleted_count += 1
                else:
                    skipped_count += 1
            else:
                logging.warning(f"Snapshot {name} not found in inventory")
                console.print(f"[bold yellow]Warning: Snapshot {name} not found in inventory[/bold yellow]")
                skipped_count += 1
        except Exception as e:
            logging.error(f"Error processing snapshot {name}: {e}")
            console.print(f"[bold red]Error processing snapshot {name}: {e}[/bold red]")
            skipped_count += 1
        finally:
            progress.update(task_id, advance=1, description=f"[cyan]Processing snapshot: {i+1}/{len(snapshot_names)}")

    return deleted_count, skipped_count

async def main():
    console.print(Panel.fit(
        Text("Azure Snapshot Management Tool", style="bold magenta"),
        border_style="cyan"
    ))

    action = Prompt.ask("Select action", choices=["Delete"], default="Delete")
    snapshot_list_file = Prompt.ask("Enter the path to the snapshot list file", default="snap_list")
    snapshot_inventory_file = Prompt.ask("Enter the path to the snapshot inventory CSV file", default="snapshots_inventory.csv")
    
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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("[cyan]Processing snapshots...", total=len(snapshot_names))
        
        deleted_count, skipped_count = await process_snapshots(snapshot_inventory, snapshot_names, progress, main_task)

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
