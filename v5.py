import asyncio
import json
import time
import logging
import csv
from concurrent.futures import ThreadPoolExecutor
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

async def get_subscriptions():
    cmd = "az account list --query '[].id' -o json"
    stdout, stderr = await run_command(cmd)
    if stderr:
        logging.error(f"Error getting subscriptions: {stderr}")
        console.print(f"[bold red]Error getting subscriptions: {stderr}[/bold red]")
        return []
    return json.loads(stdout)

def read_snapshot_list(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f]

def read_snapshot_inventory(filename):
    inventory = {}
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            inventory[row['Snapshot Name']] = row['Snapshot ID']
    return inventory

async def delete_snapshot(snapshot_id):
    try:
        delete_command = f"az resource delete --ids {snapshot_id}"
        stdout, stderr = await run_command(delete_command)
        if stderr:
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

async def delete_snapshots_from_list(snapshot_inventory, snapshot_names, progress, task_id):
    deleted_count = 0
    for i, name in enumerate(snapshot_names):
        snapshot_id = snapshot_inventory.get(name)
        if snapshot_id:
            if await delete_snapshot(snapshot_id):
                deleted_count += 1
        else:
            logging.warning(f"Snapshot {name} not found in inventory")
            console.print(f"[bold yellow]Warning: Snapshot {name} not found in inventory[/bold yellow]")
        progress.update(task_id, advance=1, description=f"[cyan]Processing snapshot: {i+1}/{len(snapshot_names)}")
    return deleted_count

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
        
        deleted_count = await delete_snapshots_from_list(snapshot_inventory, snapshot_names, progress, main_task)

    console.print(Panel(f"Total snapshots deleted: {deleted_count}", border_style="green"))
    logging.info(f"Completed deletion. Total snapshots deleted: {deleted_count}")

if __name__ == "__main__":
    try:
        start_time = time.time()
        asyncio.run(main())
        end_time = time.time()
        duration = end_time - start_time
        console.print(Panel(f"Script runtime: {duration:.2f} seconds", border_style="blue"))
        logging.info(f"Script runtime: {duration:.2f} seconds")
    except Exception as e:
        console.print(Panel(f"An error occurred: {str(e)}", border_style="red"))
        logging.error(f"Main execution error: {str(e)}")