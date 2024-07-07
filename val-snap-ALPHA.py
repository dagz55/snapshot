import os
import time
import subprocess
from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel

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

def get_resource_groups_and_subscriptions(snapshot_ids):
    resource_groups = {}
    with Progress() as progress:
        task = progress.add_task("[cyan]Getting resource groups and subscriptions...", total=len(snapshot_ids))
        for snapshot_id in snapshot_ids:
            parts = snapshot_id.split('/')
            subscription_id = parts[2]
            resource_group = parts[4]
            
            if subscription_id not in resource_groups:
                resource_groups[subscription_id] = set()
            
            resource_groups[subscription_id].add(resource_group)
            progress.update(task, advance=1)
    return resource_groups

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

def remove_scope_locks(locked_rgs):
    success_count = 0
    failed_count = 0
    logs = []
    
    with Progress() as progress:
        total = sum(len(rgs) for rgs in locked_rgs.values())
        task = progress.add_task("[cyan]Removing scope locks...", total=total)
        for subscription_id, rgs in locked_rgs.items():
            switch_subscription(subscription_id)
            for rg in rgs:
                command = f"az lock delete --name {rg}-lock --resource-group {rg}"
                result = run_az_command(command)
                if result is not None:
                    success_count += 1
                    logs.append(f"Successfully removed lock for {rg} in subscription {subscription_id}")
                else:
                    failed_count += 1
                    logs.append(f"Failed to remove lock for {rg} in subscription {subscription_id}")
                progress.update(task, advance=1)
    
    return success_count, failed_count, logs

def retry_remove_locks(failed_rgs):
    retry_count = 0
    success_count = 0
    logs = []
    
    while failed_rgs:
        retry_count += 1
        console.print(f"\n[bold yellow]Retry attempt {retry_count}[/bold yellow]")
        for subscription_id, rgs in list(failed_rgs.items()):
            switch_subscription(subscription_id)
            for rg in rgs.copy():
                lock_name = console.input(f"Enter the lock name for resource group {rg} in subscription {subscription_id}: ")
                command = f"az lock delete --name {lock_name} --resource-group {rg}"
                result = run_az_command(command)
                if result is not None:
                    success_count += 1
                    failed_rgs[subscription_id].remove(rg)
                    logs.append(f"Successfully removed lock {lock_name} for {rg} in subscription {subscription_id}")
                else:
                    logs.append(f"Failed to remove lock {lock_name} for {rg} in subscription {subscription_id}")
            
            if not failed_rgs[subscription_id]:
                del failed_rgs[subscription_id]
        
        if failed_rgs:
            retry = console.input("\nDo you want to retry removing locks? (y/n): ").lower()
            if retry != 'y':
                break
    
    return success_count, retry_count, logs

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

    resource_groups = get_resource_groups_and_subscriptions(snapshot_ids)
    total_rgs = sum(len(rgs) for rgs in resource_groups.values())
    console.print(f"\n[bold green]Found {total_rgs} unique resource groups across {len(resource_groups)} subscriptions.[/bold green]")

    locked_rgs = check_scope_locks(resource_groups)
    total_locked_rgs = sum(len(rgs) for rgs in locked_rgs.values())
    console.print(f"\n[bold green]Found {total_locked_rgs} resource groups with scope locks.[/bold green]")

    success_count, failed_count, logs = remove_scope_locks(locked_rgs)
    
    console.print(Panel(f"[bold green]Successfully removed {success_count} locks[/bold green]\n"
                        f"[bold red]Failed to remove {failed_count} locks[/bold red]",
                        title="Lock Removal Results"))

    if failed_count > 0:
        retry = console.input("\nDo you want to retry removing locks? (y/n): ").lower()
        if retry == 'y':
            retry_success, retry_count, retry_logs = retry_remove_locks(locked_rgs)
            logs.extend(retry_logs)
            console.print(Panel(f"[bold green]Successfully removed {retry_success} additional locks[/bold green]\n"
                                f"[bold cyan]Total retry attempts: {retry_count}[/bold cyan]",
                                title="Retry Results"))

    end_time = time.time()
    total_runtime = end_time - start_time

    log_filename = "lock_removal_logs.txt"
    with open(log_filename, 'w') as f:
        f.write("\n".join(logs))

    console.print(f"\n[bold blue]Total runtime: {total_runtime:.2f} seconds[/bold blue]")
    console.print(f"[bold green]Logs saved to {log_filename}[/bold green]")

if __name__ == "__main__":
    main()
