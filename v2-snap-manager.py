import asyncio
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from rich import print
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
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
        return []
    return json.loads(stdout)

async def get_snapshots(subscription_id, os_type, name_filter, retention=None):
    cmd = f"az snapshot list --subscription {subscription_id} -o json"
    if os_type != "Both":
        cmd += f" --query \"[?osType=='{os_type}']\"" 
    if name_filter:
        cmd += f" --query \"[?contains(name, '{name_filter}')]\"" 
    if retention:
        cmd += f" --query \"[?creationData.timeBeforeCurrent < '{retention}']\"" 
    
    stdout, stderr = await run_command(cmd)
    if stderr:
        logging.error(f"Error getting snapshots for subscription {subscription_id}: {stderr}")
        return []
    return json.loads(stdout)

async def delete_snapshot(subscription_id, resource_group, name):
    try:
        delete_command = f"az snapshot delete --subscription {subscription_id} --resource-group {resource_group} --name {name} --yes"
        stdout, stderr = await run_command(delete_command)
        if stderr:
            logging.error(f"Error deleting snapshot {name}: {stderr}")
        else:
            logging.info(f"Successfully deleted snapshot {name}")
    except Exception as e:
        logging.error(f"Exception occurred while deleting snapshot {name}: {e}")

async def process_subscription(subscription_id, os_type, name_filter, action, dev_retention, prod_retention, progress, task_id):
    progress.update(task_id, advance=1)
    if action == "Inventory":
        snapshots = await get_snapshots(subscription_id, os_type, name_filter)
        return [(snap['id'], snap['timeCreated'], subscription_id) for snap in snapshots]
    else:  # Delete action
        dev_snapshots = await get_snapshots(subscription_id, os_type, name_filter, dev_retention)
        prod_snapshots = await get_snapshots(subscription_id, os_type, name_filter, prod_retention)
        all_snapshots = dev_snapshots + prod_snapshots
        for snap in all_snapshots:
            await delete_snapshot(subscription_id, snap['resourceGroup'], snap['name'])
        return len(all_snapshots)

async def main():
    console.print(Panel.fit(
        Text("Azure Snapshot Management Tool", style="bold magenta"),
        border_style="cyan"
    ))

    action = Prompt.ask("Select action", choices=["Inventory", "Delete"], default="Inventory")
    os_type = Prompt.ask("Select snapshot type", choices=["Windows", "Linux", "Both"], default="Both")
    name_filter = Prompt.ask("Enter a filter for snapshot names", default="")
    
    if action == "Delete":
        dev_retention = Prompt.ask("Enter the retention period for dev snapshots (e.g., '3d')")
        prod_retention = Prompt.ask("Enter the retention period for prod snapshots (e.g., '7d')")
    else:
        dev_retention = prod_retention = None

    subscriptions = await get_subscriptions()
    console.print(Panel(f"Found [bold]{len(subscriptions)}[/bold] subscriptions", border_style="green"))
    logging.info(f"Processing {len(subscriptions)} subscriptions for {action} of {os_type} snapshots with filter: '{name_filter}'")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        main_task = progress.add_task("[cyan]Processing subscriptions...", total=len(subscriptions))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [asyncio.create_task(process_subscription(sub, os_type, name_filter, action, dev_retention, prod_retention, progress, main_task)) for sub in subscriptions]
            results = await asyncio.gather(*tasks)

    if action == "Inventory":
        all_snapshots = [item for sublist in results for item in sublist]
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