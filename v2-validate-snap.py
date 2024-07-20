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

def validate_snapshot_id(snapshot_id):
    parts = snapshot_id.split('/')
    if len(parts) < 9:
        return False, "Invalid snapshot ID format"
    return True, ""

def check_snapshot_exists(snapshot_id):
    command = f"az snapshot show --ids {snapshot_id}"
    result = run_az_command(command)
    if result.startswith("Error:"):
        return False, result
    return True, ""

def validate_snapshots(snapshot_ids):
    valid_snapshots = []
    invalid_snapshots = []

    with Progress("[bold blue]{task.description}{task.percentage:3.1f}%", BarColumn(), "[progress.completed] of {task.total}", transient=True) as progress:
        task1 = progress.add_task("Validating snapshot IDs", total=len(snapshot_ids))
        task2 = progress.add_task("Checking snapshot existence", total=len(snapshot_ids))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for snapshot_id in snapshot_ids:
                futures.append(executor.submit(validate_snapshot_id, snapshot_id))

            for future in as_completed(futures):
                is_valid, error_message = future.result()
                if is_valid:
                    valid_snapshots.append(snapshot_id)
                else:
                    invalid_snapshots.append((snapshot_id, error_message))
                progress.update(task1, advance=1)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for snapshot_id in snapshot_ids:
                futures.append(executor.submit(check_snapshot_exists, snapshot_id))

            for future in as_completed(futures):
                is_exists, error_message = future.result()
                if not is_exists:
                    invalid_snapshots.append((snapshot_id, error_message))
                progress.update(task2, advance=1)

    return valid_snapshots, invalid_snapshots

def main():
    console.print("[cyan]Azure Snapshot Validator[/cyan]")
    console.print("==========================")
    
    try:
        filename = console.input("Enter the filename with snapshot IDs: ")
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

        valid_snapshots, invalid_snapshots = validate_snapshots(snapshot_ids)

        console.print("\n[bold green]Validation Results:[/bold green]")
        console.print(f"[green]Valid Snapshots: {len(valid_snapshots)}[/green]")
        console.print(f"[red]Invalid Snapshots: {len(invalid_snapshots)}[/red]")

        if invalid_snapshots:
            console.print("\n[bold red]Invalid Snapshot Details:[/bold red]")
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("Snapshot ID", style="dim")
            table.add_column("Error", style="dim")
            for snapshot_id, error_message in invalid_snapshots:
                table.add_row(snapshot_id, error_message)
            console.print(table)

        end_time = time.time()
        total_runtime = end_time - start_time
        console.print(f"\n[bold green]Total runtime: {total_runtime:.2f} seconds[/bold green]")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}\n{traceback.format_exc()}")
        console.print(f"[red]An unexpected error occurred: {str(e)}[/red]")
        console.print("[yellow]Please check the azure_manager.log file for more details.[/yellow]")

if __name__ == "__main__":
    main()