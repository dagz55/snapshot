import os
import time
import subprocess
import json
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.table import Table

console = Console()

def run_az_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"

def get_subscription_names():
    command = "az account list --query '[].{id:id, name:name}' -o json"
    result = run_az_command(command)
    if result and not result.startswith("Error:"):
        subscriptions = json.loads(result)
        return {sub['id']: sub['name'] for sub in subscriptions}
    return {}

def validate_and_delete_snapshots(snapshot_ids, subscription_names):
    valid_snapshots = {}
    invalid_snapshots = {}
    deleted_snapshots = {}
    failed_deletions = {}

    with Progress() as progress:
        task = progress.add_task("[cyan]Validating and deleting snapshots...", total=len(snapshot_ids))
        for snapshot_id in snapshot_ids:
            parts = snapshot_id.split('/')
            subscription_id = parts[2]
            subscription_name = subscription_names.get(subscription_id, subscription_id)
            resource_group = parts[4]
            snapshot_name = parts[-1]

            # Validate snapshot
            command = f"az snapshot show --ids {snapshot_id} --query id -o tsv"
            result = run_az_command(command)
            
            if not result.startswith("Error:"):
                if subscription_name not in valid_snapshots:
                    valid_snapshots[subscription_name] = []
                valid_snapshots[subscription_name].append(snapshot_name)
                
                # Attempt to delete the snapshot
                delete_command = f"az snapshot delete -n {snapshot_name} -g {resource_group}"
                delete_result = run_az_command(delete_command)
                
                if not delete_result.startswith("Error:"):
                    if subscription_name not in deleted_snapshots:
                        deleted_snapshots[subscription_name] = []
                    deleted_snapshots[subscription_name].append(snapshot_name)
                else:
                    if subscription_name not in failed_deletions:
                        failed_deletions[subscription_name] = []
                    failed_deletions[subscription_name].append((snapshot_name, delete_result))
            else:
                if subscription_name not in invalid_snapshots:
                    invalid_snapshots[subscription_name] = []
                invalid_snapshots[subscription_name].append((snapshot_name, result))
            
            progress.update(task, advance=1)
    
    return valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions

def print_summary(valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions):
    table = Table(title="Summary")
    table.add_column("Subscription", style="cyan")
    table.add_column("Valid Snapshots", style="green")
    table.add_column("Invalid Snapshots", style="red")
    table.add_column("Deleted Snapshots", style="blue")
    table.add_column("Failed Deletions", style="yellow")

    all_subs = set(list(valid_snapshots.keys()) + list(invalid_snapshots.keys()) + 
                   list(deleted_snapshots.keys()) + list(failed_deletions.keys()))

    for subscription_name in all_subs:
        valid_count = len(valid_snapshots.get(subscription_name, []))
        invalid_count = len(invalid_snapshots.get(subscription_name, []))
        deleted_count = len(deleted_snapshots.get(subscription_name, []))
        failed_count = len(failed_deletions.get(subscription_name, []))
        table.add_row(subscription_name, str(valid_count), str(invalid_count), str(deleted_count), str(failed_count))

    console.print(table)

def print_detailed_errors(invalid_snapshots, failed_deletions):
    console.print("\n[bold red]Detailed Error Information:[/bold red]")
    
    if invalid_snapshots:
        console.print("\n[bold]Invalid Snapshots:[/bold]")
        for sub, snapshots in invalid_snapshots.items():
            console.print(f"\n[cyan]Subscription: {sub}[/cyan]")
            for snapshot, error in snapshots:
                console.print(f"  [red]• {snapshot}: {error}[/red]")
    
    if failed_deletions:
        console.print("\n[bold]Failed Deletions:[/bold]")
        for sub, snapshots in failed_deletions.items():
            console.print(f"\n[cyan]Subscription: {sub}[/cyan]")
            for snapshot, error in snapshots:
                console.print(f"  [yellow]• {snapshot}: {error}[/yellow]")

def main():
    filename = console.input("Enter the filename: ")
    if not os.path.isfile(filename):
        console.print(f"[bold red]File {filename} does not exist.[/bold red]")
        return

    start_time = time.time()

    subscription_names = get_subscription_names()
    if not subscription_names:
        console.print("[bold red]Failed to fetch subscription names. Using IDs instead.[/bold red]")

    try:
        with open(filename, 'r') as f:
            snapshot_ids = f.read().splitlines()
    except Exception as e:
        console.print(f"[bold red]Error reading file {filename}: {e}[/bold red]")
        return

    valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions = validate_and_delete_snapshots(snapshot_ids, subscription_names)
    
    total_valid = sum(len(snaps) for snaps in valid_snapshots.values())
    total_invalid = sum(len(snaps) for snaps in invalid_snapshots.values())
    total_deleted = sum(len(snaps) for snaps in deleted_snapshots.values())
    total_failed = sum(len(snaps) for snaps in failed_deletions.values())
    
    console.print(f"\n[bold green]Found {total_valid} valid snapshots.[/bold green]")
    console.print(f"[bold red]Found {total_invalid} invalid snapshots.[/bold red]")
    console.print(f"[bold blue]Successfully deleted {total_deleted} snapshots.[/bold blue]")
    console.print(f"[bold yellow]Failed to delete {total_failed} snapshots.[/bold yellow]")

    print_summary(valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions)
    print_detailed_errors(invalid_snapshots, failed_deletions)

    end_time = time.time()
    total_runtime = end_time - start_time

    console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")

if __name__ == "__main__":
    main()
