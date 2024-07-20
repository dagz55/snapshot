import os
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import logging
import traceback
import csv

console = Console()

# Set up logging
logging.basicConfig(filename='azure_manager.log', level=logging.DEBUG,
                    format='%(asctime)s:%(levelname)s:%(message)s')

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
        logging.error(f"Error in run_az_command: {str(e)}")
        return f"Error: {str(e)}"

def get_subscription_names():
    command = "az account list --query '[].{id:id, name:name}' -o json"
    result = run_az_command(command)
    if result and not result.startswith("Error:"):
        subscriptions = json.loads(result)
        return {sub['id']: sub['name'] for sub in subscriptions}
    return {}

def switch_subscription(subscription, current_subscription):
    if subscription != current_subscription:
        try:
            run_az_command(['az', 'account', 'set', '--subscription', subscription])
            console.print(f"[green]✔ Switched to subscription: {subscription}[/green]")
            return subscription
        except Exception as e:
            logging.error(f"Failed to switch to subscription {subscription}: {str(e)}")
            raise
    return current_subscription

def get_resource_groups_from_snapshots(snapshot_ids):
    resource_groups = set()
    for snapshot_id in snapshot_ids:
        parts = snapshot_id.split('/')
        if len(parts) >= 5:
            resource_groups.add((parts[2], parts[4]))  # (subscription_id, resource_group)
    return resource_groups

def check_and_remove_scope_locks(resource_groups):
    removed_locks = []
    current_subscription = None
    for subscription_id, resource_group in resource_groups:
        current_subscription = switch_subscription(subscription_id, current_subscription)
        command = f"az lock list --resource-group {resource_group} --query '[].{{name:name, level:level}}' -o json"
        locks = json.loads(run_az_command(command))
        for lock in locks:
            if lock['level'] == 'CanNotDelete':
                remove_command = f"az lock delete --name {lock['name']} --resource-group {resource_group}"
                result = run_az_command(remove_command)
                if not result.startswith("Error:"):
                    removed_locks.append((subscription_id, resource_group, lock['name']))
                    console.print(f"[green]✔ Removed lock '{lock['name']}' from resource group '{resource_group}'[/green]")
                else:
                    console.print(f"[red]Failed to remove lock '{lock['name']}' from resource group '{resource_group}': {result}[/red]")
    return removed_locks

def restore_scope_locks(removed_locks):
    current_subscription = None
    restored_locks = 0
    for subscription_id, resource_group, lock_name in removed_locks:
        current_subscription = switch_subscription(subscription_id, current_subscription)
        command = f"az lock create --name {lock_name} --resource-group {resource_group} --lock-type CanNotDelete"
        result = run_az_command(command)
        if not result.startswith("Error:"):
            console.print(f"[green]✔ Restored lock '{lock_name}' to resource group '{resource_group}'[/green]")
            restored_locks += 1
        else:
            console.print(f"[red]Failed to restore lock '{lock_name}' to resource group '{resource_group}': {result}[/red]")
    return restored_locks

def check_snapshot_exists(snapshot_id):
    command = f"az snapshot show --ids {snapshot_id}"
    result = run_az_command(command)
    return not result.startswith("Error:")

def process_snapshot(snapshot_id, subscription_names):
    try:
        parts = snapshot_id.split('/')
        if len(parts) < 9:
            logging.error(f"Invalid snapshot ID format: {snapshot_id}")
            return None, "invalid", (snapshot_id, "Invalid snapshot ID format")
        
        subscription_id = parts[2]
        subscription_name = subscription_names.get(subscription_id, subscription_id)
        snapshot_name = parts[-1]

        # Check if snapshot exists
        if not check_snapshot_exists(snapshot_id):
            return subscription_name, "non-existent", snapshot_name

        # Validate and delete snapshot
        command = f"az snapshot delete --ids {snapshot_id}"
        result = run_az_command(command)

        if not result.startswith("Error:"):
            return subscription_name, "deleted", snapshot_name
        else:
            return subscription_name, "failed", (snapshot_name, result)
    except Exception as e:
        logging.error(f"Error processing snapshot {snapshot_id}: {str(e)}")
        return None, "error", (snapshot_id, str(e))

def validate_and_delete_snapshots(snapshot_ids, subscription_names):
    results = defaultdict(lambda: defaultdict(list))

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing snapshots...", total=len(snapshot_ids))
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_snapshot = {executor.submit(process_snapshot, snapshot_id, subscription_names): snapshot_id for snapshot_id in snapshot_ids}
            for future in as_completed(future_to_snapshot):
                try:
                    subscription_name, status, data = future.result()
                    if subscription_name:
                        results[subscription_name][status].append(data)
                    else:
                        results["Unknown"][status].append(data)
                except Exception as e:
                    logging.error(f"Error processing future: {str(e)}")
                progress.update(task, advance=1)

    return results

def print_summary(results):
    table = Table(title="Summary")
    table.add_column("Subscription", style="cyan")
    table.add_column("Valid Snapshots", style="green")
    table.add_column("Non-existent Snapshots", style="yellow")
    table.add_column("Deleted Snapshots", style="blue")
    table.add_column("Failed Deletions", style="red")

    total_valid = 0
    total_non_existent = 0
    total_deleted = 0
    total_failed = 0

    for subscription_name, data in results.items():
        valid_count = len(data['deleted']) + len(data['failed'])
        non_existent_count = len(data['non-existent'])
        deleted_count = len(data['deleted'])
        failed_count = len(data['failed'])
        table.add_row(subscription_name, str(valid_count), str(non_existent_count), str(deleted_count), str(failed_count))

        total_valid += valid_count
        total_non_existent += non_existent_count
        total_deleted += deleted_count
        total_failed += failed_count

    table.add_row("Total", str(total_valid), str(total_non_existent), str(total_deleted), str(total_failed), style="bold")

    console.print(table)

def print_detailed_errors(results):
    console.print("\n[bold red]Detailed Error Information:[/bold red]")

    for subscription_name, data in results.items():
        if data['non-existent'] or data['failed'] or data['error']:
            console.print(f"\n[cyan]Subscription: {subscription_name}[/cyan]")

            if data['non-existent']:
                console.print("\n[bold]Non-existent Snapshots:[/bold]")
                for snapshot in data['non-existent']:
                    console.print(f"  [yellow]• {snapshot}[/yellow]")

            if data['failed']:
                console.print("\n[bold]Failed Deletions:[/bold]")
                for snapshot, error in data['failed']:
                    console.print(f"  [red]• {snapshot}: {error}[/red]")

            if data['error']:
                console.print("\n[bold]Errors:[/bold]")
                for snapshot, error in data['error']:
                    console.print(f"  [red]• {snapshot}: {error}[/red]")

def export_to_csv(results, filename):
    with open(filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Subscription', 'Status', 'Snapshot', 'Error'])
        for subscription, data in results.items():
            for status, snapshots in data.items():
                if status == 'deleted':
                    for snapshot in snapshots:
                        csvwriter.writerow([subscription, status, snapshot, ''])
                elif status == 'non-existent':
                    for snapshot in snapshots:
                        csvwriter.writerow([subscription, status, snapshot, 'Snapshot not found'])
                else:
                    for snapshot, error in snapshots:
                        csvwriter.writerow([subscription, status, snapshot, error])
    console.print(f"[green]✔ Results exported to {filename}[/green]")

def main():
    console.print("[cyan]Azure Snapshot Manager[/cyan]")
    console.print("=========================")
    
    try:
        filename = console.input("Enter the filename with snapshot IDs: ")
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

        if len(snapshot_ids) > 100:
            confirm = console.input(f"[yellow]You are about to process {len(snapshot_ids)} snapshots. Are you sure you want to proceed? (y/n): [/yellow]")
            if confirm.lower() != 'y':
                console.print("[red]Operation cancelled.[/red]")
                return

        resource_groups = get_resource_groups_from_snapshots(snapshot_ids)
        console.print(f"[green]✔ Found {len(resource_groups)} resource groups from snapshot list.[/green]")

        removed_locks = check_and_remove_scope_locks(resource_groups)
        console.print(f"[green]✔ Removed {len(removed_locks)} scope locks.[/green]")

        results = validate_and_delete_snapshots(snapshot_ids, subscription_names)

        console.print("[yellow]Restoring removed scope locks...[/yellow]")
        restored_locks = restore_scope_locks(removed_locks)
        console.print(f"[green]✔ Restored {restored_locks} scope locks.[/green]")

        print_summary(results)
        print_detailed_errors(results)

        end_time = time.time()
        total_runtime = end_time - start_time

        console.print(f"\n[bold green]✔ Total runtime: {total_runtime:.2f} seconds[/bold green]")
        
        export_csv = console.input("Do you want to export the results to a CSV file? (y/n): ")
        if export_csv.lower() == 'y':
            csv_filename = console.input("Enter the CSV filename to export results: ")
            export_to_csv(results, csv_filename)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}\n{traceback.format_exc()}")
        console.print(f"[red]An unexpected error occurred: {str(e)}[/red]")
        console.print("[yellow]Please check the azure_manager.log file for more details.[/yellow]")

if __name__ == "__main__":
    main()
