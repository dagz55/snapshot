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

def switch_subscription(subscription_id):
    command = f"az account set --subscription {subscription_id}"
    result = run_az_command(command)
    if result is not None:
        console.print(f"[green]Switched to subscription: {subscription_id}[/green]")
    else:
        console.print(f"[bold red]Failed to switch to subscription: {subscription_id}[/bold red]")

def validate_snapshots_and_get_rgs(snapshot_ids):
    valid_snapshots = {}
    invalid_snapshots = {}
    resource_groups = {}

    with Progress() as progress:
        task = progress.add_task("[cyan]Validating snapshots and getting resource groups...", total=len(snapshot_ids))
        for snapshot_id in snapshot_ids:
            parts = snapshot_id.split('/')
            subscription_id = parts[2]
            resource_group = parts[4]
            snapshot_name = parts[-1]

            switch_subscription(subscription_id)
            
            command = f"az snapshot show --ids {snapshot_id} --query id -o tsv"
            result = run_az_command(command)
            
            if result is not None:
                if subscription_id not in valid_snapshots:
                    valid_snapshots[subscription_id] = []
                valid_snapshots[subscription_id].append(snapshot_name)
                
                if subscription_id not in resource_groups:
                    resource_groups[subscription_id] = set()
                resource_groups[subscription_id].add(resource_group)
            else:
                if subscription_id not in invalid_snapshots:
                    invalid_snapshots[subscription_id] = []
                invalid_snapshots[subscription_id].append(snapshot_name)
            
            progress.update(task, advance=1)
    
    return valid_snapshots, invalid_snapshots, resource_groups

def check_scope_locks(resource_groups):
    locked_rgs = {}
    with Progress() as progress:
        total = sum(len(rgs) for rgs in resource_groups.values())
        task = progress.add_task("[cyan]Checking scope locks...", total=total)
        for subscription_id, rgs in resource_groups.items():
            switch_subscription(subscription_id)
            locked_rgs[subscription_id] = []
            for rg in rgs:
                command = f"az lock list --resource-group {rg} --query '[?level==`resourceGroup`]' -o tsv"
                locks = run_az_command(command)
                if locks:
                    locked_rgs[subscription_id].append(rg)
                progress.update(task, advance=1)
    return locked_rgs

def print_summary(valid_snapshots, invalid_snapshots, locked_rgs):
    table = Table(title="Summary")
    table.add_column("Subscription ID", style="cyan")
    table.add_column("Valid Snapshots", style="green")
    table.add_column("Invalid Snapshots", style="red")
    table.add_column("Locked Resource Groups", style="yellow")

    for subscription_id in set(list(valid_snapshots.keys()) + list(invalid_snapshots.keys()) + list(locked_rgs.keys())):
        valid_count = len(valid_snapshots.get(subscription_id, []))
        invalid_count = len(invalid_snapshots.get(subscription_id, []))
        locked_count = len(locked_rgs.get(subscription_id, []))
        table.add_row(subscription_id, str(valid_count), str(invalid_count), str(locked_count))

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

    valid_snapshots, invalid_snapshots, resource_groups = validate_snapshots_and_get_rgs(snapshot_ids)
    
    total_valid = sum(len(snaps) for snaps in valid_snapshots.values())
    total_invalid = sum(len(snaps) for snaps in invalid_snapshots.values())
    total_rgs = sum(len(rgs) for rgs in resource_groups.values())
    
    console.print(f"\n[bold green]Found {total_valid} valid snapshots.[/bold green]")
    console.print(f"[bold red]Found {total_invalid} invalid snapshots.[/bold red]")
    console.print(f"[bold blue]Found {total_rgs} unique resource groups across {len(resource_groups)} subscriptions.[/bold blue]")

    locked_rgs = check_scope_locks(resource_groups)
    total_locked_rgs = sum(len(rgs) for rgs in locked_rgs.values())
    console.print(f"\n[bold yellow]Found {total_locked_rgs} resource groups with scope locks.[/bold yellow]")

    print_summary(valid_snapshots, invalid_snapshots, locked_rgs)

    end_time = time.time()
    total_runtime = end_time - start_time

    console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")

if __name__ == "__main__":
    main()
