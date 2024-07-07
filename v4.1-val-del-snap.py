import os
import time
import subprocess
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
        console.print(f"[bold red]Error running command:[/bold red] {e}")
        return None

def validate_and_delete_snapshots(snapshot_ids):
    valid_snapshots = {}
    invalid_snapshots = {}
    deleted_snapshots = {}
    failed_deletions = {}

    with Progress() as progress:
        task = progress.add_task("[cyan]Validating and deleting snapshots...", total=len(snapshot_ids))
        for snapshot_id in snapshot_ids:
            parts = snapshot_id.split('/')
            subscription_id = parts[2]
            resource_group = parts[4]
            snapshot_name = parts[-1]

            # Validate snapshot
            command = f"az snapshot show --ids {snapshot_id} --query id -o tsv"
            result = run_az_command(command)
            
            if result is not None:
                if subscription_id not in valid_snapshots:
                    valid_snapshots[subscription_id] = []
                valid_snapshots[subscription_id].append(snapshot_name)
                
                # Attempt to delete the snapshot
                delete_command = f"az snapshot delete -n {snapshot_name} -g {resource_group}"
                delete_result = run_az_command(delete_command)
                
                if delete_result is not None:
                    if subscription_id not in deleted_snapshots:
                        deleted_snapshots[subscription_id] = []
                    deleted_snapshots[subscription_id].append(snapshot_name)
                else:
                    if subscription_id not in failed_deletions:
                        failed_deletions[subscription_id] = []
                    failed_deletions[subscription_id].append(snapshot_name)
            else:
                if subscription_id not in invalid_snapshots:
                    invalid_snapshots[subscription_id] = []
                invalid_snapshots[subscription_id].append(snapshot_name)
            
            progress.update(task, advance=1)
    
    return valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions

def print_summary(valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions):
    table = Table(title="Summary")
    table.add_column("Subscription", style="cyan")  # Changed from "Subscription ID" to "Subscription"
    table.add_column("Valid Snapshots", style="green")
    table.add_column("Invalid Snapshots", style="red")
    table.add_column("Deleted Snapshots", style="blue")
    table.add_column("Failed Deletions", style="yellow")

    all_subs = set(list(valid_snapshots.keys()) + list(invalid_snapshots.keys()) + 
                   list(deleted_snapshots.keys()) + list(failed_deletions.keys()))

    for subscription_id in all_subs:
        valid_count = len(valid_snapshots.get(subscription_id, []))
        invalid_count = len(invalid_snapshots.get(subscription_id, []))
        deleted_count = len(deleted_snapshots.get(subscription_id, []))
        failed_count = len(failed_deletions.get(subscription_id, []))
        table.add_row(subscription_id, str(valid_count), str(invalid_count), str(deleted_count), str(failed_count))

    console.print(table)

def main():
    filename = console.input("Enter the filename: ")
    if not os.path.isfile(filename):
        console.print(f"[bold red]File {filename} does not exist.[/bold red]")
        return

    start_time = time.time()

    try:
        with open(filename, 'r') as f:
            snapshot_ids = f.read().splitlines()
    except Exception as e:
        console.print(f"[bold red]Error reading file {filename}: {e}[/bold red]")
        return

    valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions = validate_and_delete_snapshots(snapshot_ids)
    
    total_valid = sum(len(snaps) for snaps in valid_snapshots.values())
    total_invalid = sum(len(snaps) for snaps in invalid_snapshots.values())
    total_deleted = sum(len(snaps) for snaps in deleted_snapshots.values())
    total_failed = sum(len(snaps) for snaps in failed_deletions.values())
    
    console.print(f"\n[bold green]Found {total_valid} valid snapshots.[/bold green]")
    console.print(f"[bold red]Found {total_invalid} invalid snapshots.[/bold red]")
    console.print(f"[bold blue]Successfully deleted {total_deleted} snapshots.[/bold blue]")
    console.print(f"[bold yellow]Failed to delete {total_failed} snapshots.[/bold yellow]")

    print_summary(valid_snapshots, invalid_snapshots, deleted_snapshots, failed_deletions)

    end_time = time.time()
    total_runtime = end_time - start_time

    console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")

if __name__ == "__main__":
    main()
