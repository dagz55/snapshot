import os
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, BarColumn
from rich.table import Table
import logging
import traceback
import csv

console = Console()

def run_az_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"

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

    with Progress("[bold blue]{task.description}", BarColumn(), "{task.completed}/{task.total}", console=console) as progress:
        task1 = progress.add_task("Validating snapshot IDs", total=len(snapshot_ids))
        task2 = progress.add_task("Checking snapshot existence", total=len(snapshot_ids))

        for snapshot_id in snapshot_ids:
            is_valid, error_message = validate_snapshot_id(snapshot_id)
            if is_valid:
                valid_snapshots.append(snapshot_id)
            else:
                invalid_snapshots.append((snapshot_id, error_message))
            progress.update(task1, advance=1)
            console.print(f"Validated ID: {snapshot_id}")

        for snapshot_id in valid_snapshots.copy():
            exists, error_message = check_snapshot_exists(snapshot_id)
            if not exists:
                valid_snapshots.remove(snapshot_id)
                invalid_snapshots.append((snapshot_id, error_message))
            progress.update(task2, advance=1)
            console.print(f"Checked existence: {snapshot_id}")

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

        if not snapshot_ids:
            console.print("[bold yellow]No snapshot IDs found in the file. Please check the file content.[/bold yellow]")
            return

        console.print(f"[green]Found {len(snapshot_ids)} snapshot IDs in the file.[/green]")
        console.print("[yellow]Starting validation process...[/yellow]")

        valid_snapshots, invalid_snapshots = validate_snapshots(snapshot_ids)

        console.print("\n[bold green]Validation Results:[/bold green]")
        console.print(f"[green]Valid Snapshots: {len(valid_snapshots)}[/green]")
        console.print(f"[red]Invalid Snapshots: {len(invalid_snapshots)}[/red]")

        # Save results to CSV
        results_file = "snapshot_validation_results.csv"
        with open(results_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Snapshot ID', 'Status', 'Error'])
            for snapshot_id in valid_snapshots:
                writer.writerow([snapshot_id, 'Valid', ''])
            for snapshot_id, error in invalid_snapshots:
                writer.writerow([snapshot_id, 'Invalid', error])
        
        console.print(f"[green]Results saved to {results_file}[/green]")

        # Prompt user if they want to see invalid snapshot details
        if invalid_snapshots:
            show_details = console.input("\nDo you want to see the invalid snapshot details? (y/n): ").lower()
            if show_details == 'y':
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
