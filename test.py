import os
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

console = Console()

def run_az_command(command):
    try:
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            stdout, stderr = process.communicate()
        if process.returncode != 0:
            return f"Error: {stderr.strip()}"
        return stdout.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def get_subscription_names():
    command = "az account list --query '[].{id:id, name:name}' -o json"
    result = run_az_command(command)
    if result and not result.startswith("Error:"):
        subscriptions = json.loads(result)
        return {sub['id']: sub['name'] for sub in subscriptions}
    return {}

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

    results = validate_and_delete_snapshots(snapshot_ids, subscription_names)
    print_summary(results)
    print_detailed_errors(results)

    end_time = time.time()
    total_runtime = end_time - start_time

    console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")

if __name__ == "__main__":
    main()
