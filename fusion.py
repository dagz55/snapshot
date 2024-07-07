import subprocess
import json
from rich.console import Console
from rich.table import Table
from tabulate import tabulate
import logging
from typing import Dict, List, Tuple
import asyncio
import aiohttp

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

async def run_az_command(command: List[str]) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stderr)
        return stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.cmd}. Error: {e.stderr}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise

async def switch_subscription(subscription: str) -> None:
    try:
        await run_az_command(['az', 'account', 'set', '--subscription', subscription])
        console.print(f"[yellow]Switched to subscription: {subscription}[/yellow]")
    except Exception as e:
        logging.error(f"Failed to switch to subscription {subscription}: {str(e)}")
        raise

async def check_lock_exists(rg: str, lock: str) -> bool:
    try:
        result = await run_az_command(['az', 'lock', 'show', '--name', lock, '--resource-group', rg])
        return bool(result)
    except subprocess.CalledProcessError:
        return False

async def manage_lock(rg: str, lock: str, action: str) -> Tuple[bool, str]:
    try:
        if action == 'delete':
            if await check_lock_exists(rg, lock):
                await run_az_command(['az', 'lock', 'delete', '--name', lock, '--resource-group', rg])
                return True, f"[green]✅ Deleted scope lock '{lock}' for resource group '{rg}'[/green]"
            else:
                return True, f"[yellow]⚠️ Scope lock '{lock}' does not exist for resource group '{rg}'[/yellow]"
        elif action == 'restore':
            if not await check_lock_exists(rg, lock):
                await run_az_command(['az', 'lock', 'create', '--name', lock, '--resource-group', rg, '--lock-type', 'CanNotDelete'])
                return True, f"[green]✅ Restored scope lock '{lock}' for resource group '{rg}'[/green]"
            else:
                return True, f"[yellow]⚠️ Scope lock '{lock}' already exists for resource group '{rg}'[/yellow]"
        else:
            return False, f"[red]❌ Invalid action '{action}' for scope lock '{lock}' on resource group '{rg}'[/red]"
    except Exception as e:
        return False, f"[red]❌ Failed to {action} scope lock '{lock}' for resource group '{rg}': {str(e)}[/red]"

async def manage_scope_locks(action: str) -> None:
    summary: Dict[str, Dict[str, int]] = {sub: {"Processed": 0, "Succeeded": 0, "Failed": 0} for sub in resource_groups.keys()}
    detailed_errors: Dict[str, List[Tuple[str, str, str]]] = {}

    async with aiohttp.ClientSession() as session:
        for subscription, rgs in resource_groups.items():
            try:
                await switch_subscription(subscription)
                tasks = []
                for rg, lock in rgs.items():
                    task = asyncio.create_task(manage_lock(rg, lock, action))
                    tasks.append((rg, lock, task))

                for rg, lock, task in tasks:
                    summary[subscription]["Processed"] += 1
                    success, message = await task
                    console.print(message)
                    if success:
                        summary[subscription]["Succeeded"] += 1
                    else:
                        summary[subscription]["Failed"] += 1
                        if subscription not in detailed_errors:
                            detailed_errors[subscription] = []
                        detailed_errors[subscription].append((rg, lock, message))

            except Exception as e:
                console.print(f"[red]❌ Failed to process subscription '{subscription}': {str(e)}[/red]")
                summary[subscription]["Failed"] += len(rgs)
                if subscription not in detailed_errors:
                    detailed_errors[subscription] = []
                detailed_errors[subscription].extend([(rg, lock, str(e)) for rg, lock in rgs.items()])

    print_summary(summary, detailed_errors)

def print_summary(summary: Dict[str, Dict[str, int]], detailed_errors: Dict[str, List[Tuple[str, str, str]]]) -> None:
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
                console.print(f"  • {rg} - {lock}: {error}")

async def main() -> None:
    console.print("[cyan]Azure Resource Manager[/cyan]")
    console.print("=========================")
    
    try:
        while True:
            action = console.input("[yellow]Enter 'lock' to manage scope locks or 'quit' to exit: [/yellow]").lower()
            
            if action == 'lock':
                lock_action = console.input("[yellow]Enter 'delete' to remove scope locks or 'restore' to add them back: [/yellow]").lower()
                if lock_action in ['delete', 'restore']:
                    await manage_scope_locks(lock_action)
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
    asyncio.run(main())
