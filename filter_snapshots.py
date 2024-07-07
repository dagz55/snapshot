import csv
from datetime import datetime, timedelta
from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table

console = Console()

def parse_date(date_string):
    return datetime.strptime(date_string.split('.')[0], "%Y-%m-%dT%H:%M:%S")

def filter_snapshots(days):
    filtered_snapshots = []
    cutoff_date = datetime.now(datetime.utcnow().tzinfo) - timedelta(days=days)
    
    with open('snapshots_inventory.csv', 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)  # Skip header
        
        for row in csv_reader:
            snapshot_id, creation_date, subscription_id = row
            snapshot_date = parse_date(creation_date)
            
            if snapshot_date <= cutoff_date:
                filtered_snapshots.append(row)
    
    return filtered_snapshots

def main():
    console.print("[bold]Snapshot Inventory Filter[/bold]")
    
    days = IntPrompt.ask("Enter the number of days (snapshots older than this will be listed)")
    
    filtered_snapshots = filter_snapshots(days)
    
    if not filtered_snapshots:
        console.print(f"[yellow]No snapshots found older than {days} days.[/yellow]")
    else:
        table = Table(title=f"Snapshots Older Than {days} Days")
        table.add_column("Snapshot ID", style="cyan", no_wrap=True)
        table.add_column("Creation Date", style="magenta")
        table.add_column("Subscription ID", style="green")
        
        for snapshot in filtered_snapshots:
            table.add_row(snapshot[0], snapshot[1], snapshot[2])
        
        console.print(table)
        console.print(f"[bold green]Total snapshots found: {len(filtered_snapshots)}[/bold green]")
        
        # Option to save filtered results
        if console.input("Do you want to save these results to a new CSV file? (y/n): ").lower() == "y":
            output_file = f"snapshots_older_than_{days}_days.csv"
            with open(output_file, 'w', newline='') as file:
                csv_writer = csv.writer(file)
                csv_writer.writerow(["Snapshot ID", "Creation Date", "Subscription ID"])
                csv_writer.writerows(filtered_snapshots)
            console.print(f"[bold green]Results saved to {output_file}[/bold green]")

if __name__ == "__main__":
    main()
