import os
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from colorama import init, Fore, Style
from tabulate import tabulate
import logging

# Initialize colorama for cross-platform color support
init()

console = Console()

# Set up logging
logging.basicConfig(filename='azure_manager.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# Resource Groups and their corresponding lock names, with hard-coded subscriptions
resource_groups = {
    "az-entapp-prod-01": {
        "az-entapp-prod-01-fdfr-prod-westus-rg-01": "az-entapp-prod-01-fdfr-prod-westus-rg-01-lock"
    },
    "az-entaks-prod-01": {
        "az-entaks-prod-01-dasc-prod-eastus-rg-01": "az-entaks-prod-01-dasc-prod-eastus-rg-01-lock",
        "az-entaks-prod-01-dasc-prod-westus-rg-01": "az-entaks-prod-01-dasc-prod-westus-rg-01-lock",
        "az-entaks-prod-01-sp2k-prod-westus-rg-01": "az-entaks-prod-01-sp2k-prod-westus-rg-01-lock"
    },
    "az-core-prod-01": {
        "az-core-prod-01-scsb-prod-eastus-rg-01": "az-core-prod-01-scsb-prod-eastus-rg-01-lock",
        "az-core-prod-01-esat-prod-westus-rg-01": "az-core-prod-01-esat-prod-westus-rg-01-lock"
    },
    "az-resibm-prod-01": {
        "az-resibm-prod-01-ebis-prod-westus-rg-01": "az-resibm-prod-01-ebis-prod-westus-rg-01-lock"
    }
}

def run_az_command(command):
    try:
        if isinstance(command, list):
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        else:
            with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                stdout, stderr = process.communicate()
            if process.returncode != 0:
                return f"Error: {stderr.strip()}"
            return stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.cmd}. Error: {e.stderr}")
        raise
    except Exception as e:
        return f"Error: {str(e)}"

def get_subscription_names():
    command = "az account list --query '[].{id:id, name:name}' -o json"
    result = run_az_command(command)
    if result and not result.startswith("Error:"):
        subscriptions = json.loads(result)
        return {sub['id']: sub['name'] for sub in subscriptions}
    return {}

def switch_subscription(subscription):
    try:
        run_az_command(['az', 'account', 'set', '--subscription', subscription])
        console.print(f"[yellow]Switched to subscription: {subscription}[/yellow]")
    except Exception as e:
        logging.error(f"Failed to switch to subscription {subscription}: {str(e)}")
        raise

def process_snapshot(snapshot_id, subscription_names):
    parts = snapshot_id.split('/')
    subscription_id = parts[2]
    subscription_name = subscription_names.get(subscription_id, subscription_id)
    resource_group = parts[4]
    snapshot_name = parts[-1]

    # Validate and delete snapshot
    command = f"az snapshot delete --ids {snapshot_id}"
    result = run_az_command(command)

    if not result.startswith("Error:"):
        return subscription_name, "deleted", snapshot_name
    elif "ResourceNotFound" in result:
        return subscription_name, "invalid", (snapshot_name, result)
    else:
        return subscription_name, "failed", (snapshot_name, result)

def validate_and_delete_snapshots(snapshot_ids, subscription_names):
    results = defaultdict(lambda: defaultdict(list))

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing snapshots...", total=len(snapshot_ids))
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_snapshot = {executor.submit(process_snapshot, snapshot_id, subscription_names): snapshot_id for snapshot_id in snapshot_ids}
            for future in as_completed(future_to_snapshot):
                subscription_name, status, data = future.result()
                results[subscription_name][status].append(data)
                progress.update(task, advance=1)

    return results

def print_summary(results):
    table = Table(title="Summary")
    table.add_column("Subscription", style="cyan")
    table.add_column("Valid Snapshots", style="green")
    table.add_column("Invalid Snapshots", style="red")
    table.add_column("Deleted Snapshots", style="blue")
    table.add_column("Failed Deletions", style="yellow")

    for subscription_name, data in results.items():
        valid_count = len(data['deleted'])
        invalid_count = len(data['invalid'])
        deleted_count = len(data['deleted'])
        failed_count = len(data['failed'])
        table.add_row(subscription_name, str(valid_count), str(invalid_count), str(deleted_count), str(failed_count))

    console.print(table)

def print_detailed_errors(results):
    console.print("\n[bold red]Detailed Error Information:[/bold red]")

    for subscription_name, data in results.items():
        if data['invalid'] or data['failed']:
            console.print(f"\n[cyan]Subscription: {subscription_name}[/cyan]")

            if data['invalid']:
                console.print("\n[bold]Invalid Snapshots:[/bold]")
                for snapshot, error in data['invalid']:
                    console.print(f"  [red]• {snapshot}: {error}[/red]")

            if data['failed']:
                console.print("\n[bold]Failed Deletions:[/bold]")
                for snapshot, error in data['failed']:
                    console.print(f"  [yellow]• {snapshot}: {error}[/yellow]")

def manage_scope_locks(action):
    summary = {sub: {"Processed": 0, "Succeeded": 0, "Failed": 0} for sub in resource_groups.keys()}
    detailed_errors = {}

    for subscription, rgs in resource_groups.items():
        try:
            switch_subscription(subscription)

            for rg, lock in rgs.items():
                summary[subscription]["Processed"] += 1
                try:
                    if action == 'delete':
                        run_az_command(['az', 'lock', 'delete', '--name', lock, '--resource-group', rg])
                        console.print(f"[green]✅ Deleted scope lock '{lock}' for resource group '{rg}'[/green]")
                    else:
                        run_az_command(['az', 'lock', 'create', '--name', lock, '--resource-group', rg, '--lock-type', 'CanNotDelete'])
                        console.print(f"[green]✅ Restored scope lock '{lock}' for resource group '{rg}'[/green]")
                    summary[subscription]["Succeeded"] += 1
                except Exception as e:
                    summary[subscription]["Failed"] += 1
                    error_msg = f"[red]❌ Failed to {'delete' if action == 'delete' else 'restore'} scope lock '{lock}' for resource group '{rg}': {str(e)}[/red]"
                    console.print(error_msg)
                    if subscription not in detailed_errors:
                        detailed_errors[subscription] = []
                    detailed_errors[subscription].append((rg, lock, str(e)))
        except Exception as e:
            console.print(f"[red]❌ Failed to process subscription '{subscription}': {str(e)}[/red]")
            summary[subscription]["Failed"] += len(rgs)
            if subscription not in detailed_errors:
                detailed_errors[subscription] = []
            detailed_errors[subscription].extend([(rg, lock, str(e)) for rg, lock in rgs.items()])

    console.print("\nSummary")
    console.print("-------")
    table_data = [
        [sub, data["Processed"], data["Succeeded"], data["Failed"]]
        for sub, data in summary.items()
    ]
    console.print(tabulate(table_data, headers=["Subscription", "Processed", "Succeeded", "Failed"], tablefmt="grid"))

    if detailed_errors:
        console.print("\nDetailed Error Information:")
        for sub, errors in detailed_errors.items():
            console.print(f"\nSubscription: {sub}")
            console.print("Failed Operations:")
            for rg, lock, error in errors:
                console.print(f"  • {rg} - {lock}: Error: {error}")

def main():
    console.print("[cyan]Azure Resource Manager[/cyan]")
    console.print("=========================")
    
    try:
        while True:
            action = console.input("[yellow]Enter 'snapshot' to manage snapshots, 'lock' to manage scope locks, or 'quit' to exit: [/yellow]").lower()
            
            if action == 'snapshot':
                filename = console.input("Enter the filename with snapshot IDs: ")
                if not os.path.isfile(filename):
                    console.print(f"[bold red]File {filename} does not exist.[/bold red]")
                    continue

                start_time = time.time()

                subscription_names = get_subscription_names()
                if not subscription_names:
                    console.print("[bold red]Failed to fetch subscription names. Using IDs instead.[/bold red]")

                try:
                    with open(filename, 'r') as f:
                        snapshot_ids = f.read().splitlines()
                except Exception as e:
                    console.print(f"[bold red]Error reading file {filename}: {e}[/bold red]")
                    continue

                results = validate_and_delete_snapshots(snapshot_ids, subscription_names)
                print_summary(results)
                print_detailed_errors(results)

                end_time = time.time()
                total_runtime = end_time - start_time

                console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")

            elif action == 'lock':
                lock_action = console.input("[yellow]Enter 'delete' to remove scope locks or 'restore' to add them back: [/yellow]").lower()
                if lock_action in ['delete', 'restore']:
                    manage_scope_locks(lock_action)
                else:
                    console.print("[red]Invalid input. Please try again.[/red]")

            elif action == 'quit':
                break
            else:
                console.print("[red]Invalid input. Please try again.[/red]")
        
        console.print("[yellow]Operation completed. Check the log file for details.[/yellow]")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        console.print(f"[red]An unexpected error occurred: {str(e)}[/red]")

if __name__ == "__main__":
    main()
