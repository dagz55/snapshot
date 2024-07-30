import os
import subprocess
import argparse
from tabulate import tabulate

def setup_venv():
    subprocess.run(["python", "-m", "venv", "snapvenv"])
    subprocess.run(["snapvenv/bin/activate"])
    subprocess.run(["pip3", "install", "--upgrade", "pip"])
    subprocess.run(["pip", "install", "-r", "requirements.txt"])

def validate_snapshots():
    if not os.path.exists("validate_snap/snapshot_list.txt"):
        print("snapshot_list.txt not found. Creating an empty file.")
        with open("validate_snap/snapshot_list.txt", "w") as file:
            pass
    subprocess.run(["python", "validate_snap/validate-snap.py"])

def create_snapshots():
    subprocess.run(["python", "create-snap/az_create-snap-promax.py"])

def delete_snapshots():
    subprocess.run(["python", "az-delete-snapshot-BETA.py"])

def main():
    parser = argparse.ArgumentParser(description="Snapshot Management Menu")
    parser.add_argument("operation", choices=["validate", "create", "delete", "exit"], help="Choose an operation")

    args = parser.parse_args()

    if not os.path.exists("snapvenv"):
        setup_venv()

    if args.operation == "validate":
        validate_snapshots()
    elif args.operation == "create":
        create_snapshots()
    elif args.operation == "delete":
        delete_snapshots()
    elif args.operation == "exit":
        print("Exiting...")
        return

    # Add runtime checks before and after the migration

    # Add error handling

    # Display run summary as a table
    summary = [
        ["Operation", args.operation],
        ["Status", "Success"],
        # Add more summary data as needed
    ]
    print(tabulate(summary, headers=["Attribute", "Value"], tablefmt="grid"))

    # Add prompt to ask the user if they want to save the log file

if __name__ == "__main__":
    main()
