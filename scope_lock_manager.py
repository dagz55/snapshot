import subprocess
import json
from colorama import init, Fore, Style
from tabulate import tabulate
import logging

# Initialize colorama for cross-platform color support
init()

# Set up logging
logging.basicConfig(filename='scope_lock_manager.log', level=logging.INFO,
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
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.cmd}. Error: {e.stderr}")
        raise

def switch_subscription(subscription):
    try:
        run_az_command(['az', 'account', 'set', '--subscription', subscription])
        print(f"{Fore.YELLOW}Switched to subscription: {subscription}{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"Failed to switch to subscription {subscription}: {str(e)}")
        raise

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
                        print(f"{Fore.GREEN}✅ Deleted scope lock '{lock}' for resource group '{rg}'{Style.RESET_ALL}")
                    else:
                        run_az_command(['az', 'lock', 'create', '--name', lock, '--resource-group', rg, '--lock-type', 'CanNotDelete'])
                        print(f"{Fore.GREEN}✅ Restored scope lock '{lock}' for resource group '{rg}'{Style.RESET_ALL}")
                    summary[subscription]["Succeeded"] += 1
                except Exception as e:
                    summary[subscription]["Failed"] += 1
                    error_msg = f"{Fore.RED}❌ Failed to {'delete' if action == 'delete' else 'restore'} scope lock '{lock}' for resource group '{rg}': {str(e)}{Style.RESET_ALL}"
                    print(error_msg)
                    if subscription not in detailed_errors:
                        detailed_errors[subscription] = []
                    detailed_errors[subscription].append((rg, lock, str(e)))
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to process subscription '{subscription}': {str(e)}{Style.RESET_ALL}")
            summary[subscription]["Failed"] += len(rgs)
            if subscription not in detailed_errors:
                detailed_errors[subscription] = []
            detailed_errors[subscription].extend([(rg, lock, str(e)) for rg, lock in rgs.items()])

    print("\nSummary")
    print("-------")
    table_data = [
        [sub, data["Processed"], data["Succeeded"], data["Failed"]]
        for sub, data in summary.items()
    ]
    print(tabulate(table_data, headers=["Subscription", "Processed", "Succeeded", "Failed"], tablefmt="grid"))

    if detailed_errors:
        print("\nDetailed Error Information:")
        for sub, errors in detailed_errors.items():
            print(f"\nSubscription: {sub}")
            print("Failed Operations:")
            for rg, lock, error in errors:
                print(f"  • {rg} - {lock}: Error: {error}")

def main():
    print(f"{Fore.CYAN}Azure Scope Lock Manager{Style.RESET_ALL}")
    print("=========================")
    
    try:
        while True:
            action = input(f"{Fore.YELLOW}Enter 'delete' to remove scope locks, 'restore' to add them back, or 'quit' to exit: {Style.RESET_ALL}").lower()
            
            if action in ['delete', 'restore']:
                manage_scope_locks(action)
            elif action == 'quit':
                break
            else:
                print(f"{Fore.RED}Invalid input. Please try again.{Style.RESET_ALL}")
        
        print(f"{Fore.YELLOW}Operation completed. Check the log file for details.{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        print(f"{Fore.RED}An unexpected error occurred: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
