import asyncio
import json
import time
import logging
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
        return [line.split()[0] for line in f]

async def get_snapshot_info(subscription_id, name):
    cmd = f"az snapshot show --subscription {subscription_id} --name {name} -o json"
    stdout, stderr = await run_command(cmd)
    if stderr:
        logging.error(f"Error getting info for snapshot {name}: {stderr}")
        console.print(f"[bold red]Error getting info for snapshot {name}: {stderr}[/bold red]")
        return None
    return json.loads(stdout)

async def delete_snapshot(subscription_id, name):
    try:
        # First, get the snapshot info to retrieve the resource group
        snapshot_info = await get_snapshot_info(subscription_id, name)
        if not snapshot_info:
            return False
        
        resource_group = snapshot_info.get('resourceGroup')
        if not resource_group:
            logging.error(f"Could not determine resource group for snapshot {name}")
            console.print(f"[bold red]Could not determine resource group for snapshot {name}[/bold red]")
            return False

        delete_command = f"az snapshot delete --subscription {subscription_id} --name {name} --resource-group {resource_group}"
        stdout, stderr = await run_command(delete_command)
        if stderr:
            logging.error(f"Error deleting snapshot {name}: {stderr}")
            console.print(f"[bold red]Error deleting snapshot {name}: {stderr}[/bold red]")
            return False
        else:
            logging.info(f"Successfully deleted snapshot {name}")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while deleting snapshot {name}: {e}")
        console.print(f"[bold red]Exception occurred while deleting snapshot {name}: {e}[/bold red]")
        return False

async def delete_snapshots_from_list(subscription_id, snapshot_names, progress, task_id):
    deleted_count = 0
    for i, name in enumerate(snapshot_names):
        if await delete_snapshot(subscription_id, name):
            deleted_count += 1
        progress.update(task_id, advance=1, description=f"[cyan]Processing subscription {subscription_id}: {i+1}/{len(snapshot_names)}")
    return deleted_count

async def process_snapshots(subscription_id, snapshot_names, action, progress, task_id):
    if action == "Inventory":
        results = []
        for i, name in enumerate(snapshot_names):
            info = await get_snapshot_info(subscription_id, name)
            if info:
                results.append((info['id'], info['timeCreated'], subscription_id))
            progress.update(task_id, advance=1, description=f"[cyan]Processing subscription {subscription_id}: {i+1}/{len(snapshot_names)}")
        return results
    else:  # Delete action
        return await delete_snapshots_from_list(subscription_id, snapshot_names, progress, task_id)

async def main():
    console.print(Panel.fit(
        Text("Azure Snapshot Management Tool", style="bold magenta"),
        border_style="cyan"
    ))

    action = Prompt.ask("Select action", choices=["Inventory", "Delete"], default="Delete")
    snapshot_list_file = Prompt.ask("Enter the path to the snapshot list file", default="snap_list")
    
    snapshot_names = read_snapshot_list(snapshot_list_file)
    console.print(Panel(f"Found [bold]{len(snapshot_names)}[/bold] snapshots in the list", border_style="green"))

    subscriptions = await get_subscriptions()
    console.print(Panel(f"Found [bold]{len(subscriptions)}[/bold] subscriptions", border_style="green"))
    logging.info(f"Processing {len(subscriptions)} subscriptions for {action} of {len(snapshot_names)} snapshots")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        main_task = progress.add_task("[cyan]Processing subscriptions...", total=len(subscriptions) * len(snapshot_names))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [asyncio.create_task(process_snapshots(sub, snapshot_names, action, progress, main_task)) for sub in subscriptions]
            results = await asyncio.gather(*tasks)

    if action == "Inventory":
        all_snapshots = [item for sublist in results if sublist for item in sublist]
        all_snapshots.sort(key=lambda x: x[1])

        with open('snapshots_inventory.csv', 'w') as f:
            f.write("Snapshot ID,Creation Date,Subscription ID\n")
            for snapshot in all_snapshots:
                f.write(f"{snapshot[0]},{snapshot[1]},{snapshot[2]}\n")

        console.print(Panel(f"Total snapshots found: {len(all_snapshots)}", border_style="green"))
        console.print(Panel("Results written to snapshots_inventory.csv", border_style="green"))
        logging.info(f"Completed inventory. Total snapshots found: {len(all_snapshots)}")
    else:
        total_deleted = sum(results)
        console.print(Panel(f"Total snapshots deleted: {total_deleted}", border_style="green"))
        logging.info(f"Completed deletion. Total snapshots deleted: {total_deleted}")

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