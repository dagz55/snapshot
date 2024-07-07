import asyncio
import json
import subprocess
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.console import Console
from rich.prompt import Prompt

# Configure logging
logging.basicConfig(filename='snapshot_inventory.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

console = Console()

async def run_command(cmd):
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if stderr:
            logging.error(f"Error in command: {cmd}\nError: {stderr.decode()}")
        return stdout.decode(), stderr.decode()
    except Exception as e:
        logging.error(f"Exception in run_command: {str(e)}")
        return "", str(e)

async def get_subscriptions():
    cmd = "az account list --query '[].id' -o json"
    stdout, stderr = await run_command(cmd)
    return json.loads(stdout)

async def get_snapshots(subscription_id, os_type):
    if os_type == 'Both':
        cmd = f"az snapshot list --subscription {subscription_id} -o json"
    else:
        cmd = f"az snapshot list --subscription {subscription_id} --query \"[?osType=='{os_type}']\" -o json"
    stdout, stderr = await run_command(cmd)
    return json.loads(stdout)

async def process_subscription(subscription_id, os_type, progress, task_id):
    try:
        snapshots = await get_snapshots(subscription_id, os_type)
        progress.update(task_id, advance=1)
        return [(s['id'], s['timeCreated'], subscription_id) for s in snapshots]
    except Exception as e:
        logging.error(f"Error processing subscription {subscription_id}: {str(e)}")
        progress.update(task_id, advance=1)
        return []

async def main():
    os_type = Prompt.ask("Select snapshot type", choices=["Windows", "Linux", "Both"], default="Both")
    
    subscriptions = await get_subscriptions()
    console.print(f"Found [bold]{len(subscriptions)}[/bold] subscriptions")
    logging.info(f"Processing {len(subscriptions)} subscriptions for {os_type} snapshots")

    all_snapshots = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        main_task = progress.add_task("[cyan]Processing subscriptions...", total=len(subscriptions))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [asyncio.create_task(process_subscription(sub, os_type, progress, main_task)) for sub in subscriptions]
            results = await asyncio.gather(*tasks)
            for result in results:
                all_snapshots.extend(result)

    # Sort snapshots by creation date
    all_snapshots.sort(key=lambda x: x[1])

    # Write results to file
    with open('snapshots_inventory.csv', 'w') as f:
        f.write("Snapshot ID,Creation Date,Subscription ID\n")
        for snapshot in all_snapshots:
            f.write(f"{snapshot[0]},{snapshot[1]},{snapshot[2]}\n")

    console.print(f"[green]Total snapshots found: {len(all_snapshots)}[/green]")
    console.print("[green]Results written to snapshots_inventory.csv[/green]")
    logging.info(f"Completed. Total snapshots found: {len(all_snapshots)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"[bold red]An error occurred: {str(e)}[/bold red]")
        logging.error(f"Main execution error: {str(e)}")
