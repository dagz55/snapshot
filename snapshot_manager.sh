#!/bin/bash

# Function to create and activate virtual environment
setup_venv() {
    python -m venv snapvenv
    source snapvenv/bin/activate
    pip3 install --upgrade pip
    pip install -r requirements.txt
}

# Function to validate snapshots
validate_snapshots() {
    python validate_snap/validate-snap.py
}

# Function to create snapshots
create_snapshots() {
    python create-snap/az_create-snap-promax.py
}

# Function to delete snapshots
delete_snapshots() {
    python az-delete-snapshot-BETA.py
}

# Setup virtual environment if it doesn't exist
if [ ! -d "snapvenv" ]; then
    setup_venv
else
    source snapvenv/bin/activate
fi

# Main menu loop
while true; do
    echo "Snapshot Management Menu"
    echo "1. Validate Snapshots"
    echo "2. Create Snapshots"
    echo "3. Delete Snapshots"
    echo "4. Exit"
    read -p "Please enter your choice (1-4): " choice

    case $choice in
        1)
            validate_snapshots
            ;;
        2)
            create_snapshots
            ;;
        3)
            delete_snapshots
            ;;
        4)
            echo "Exiting..."
            deactivate
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            ;;
    esac

    echo
done