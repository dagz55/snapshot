# [Ep.01 The Deletion 🗑️]

# 🔷 Azure Snapshot Deletion Manager 🔷

Efficiently manage and delete Azure snapshots across multiple subscriptions!

## 📋 Description

Azure Snapshot Manager is a powerful Python script that helps you validate and delete Azure snapshots across multiple subscriptions. It provides a user-friendly interface with progress tracking, detailed summaries, and error reporting.

## ✨ Features

- 🔍 Validate snapshot IDs across multiple subscriptions
- 🗑️ Delete valid snapshots efficiently
- 🔒 Automatically handle scope locks (remove before deletion, restore after)
- 📊 Generate summary reports of processed snapshots
- 🚨 Provide detailed error information for invalid or failed deletions
- 🖥️ User-friendly console interface with progress tracking

## 🛠️ Requirements

### Python Version

This script is compatible with Python 3.6+. No specific version is required, but using the latest stable version of Python 3 is recommended.

### Required Modules

The following Python modules are required to run the Azure Snapshot Manager:

- os (built-in)
- time (built-in)
- subprocess (built-in)
- json (built-in)
- concurrent.futures (built-in)
- collections (built-in)
- rich
- logging (built-in)

### External Dependencies

- Azure CLI (az command-line tool) must be installed and configured on your system.

## 🚀 Installation

1. Clone this repository:
   ```
   git clone https://github.com/dagz55/snapshot.git
   ```

2. Navigate to the project directory:
   ```
   cd snapshot
   ```

3. Install the required Python packages:
   ```
   pip install rich
   ```

4. Ensure you have the Azure CLI installed and configured with the necessary permissions.

## 📝 Usage

1. Prepare a text file with a list of snapshot IDs, one per line.

2. Run the script:
   ```
   python azure_snapshot_manager.py
   ```

3. When prompted, enter the filename containing the snapshot IDs.

4. The script will process the snapshots, providing real-time progress updates and a summary upon completion.

## 📊 Output

The script provides:
- A progress bar during snapshot processing
- A summary table of processed snapshots
- Detailed error information for invalid snapshots or failed deletions
- Total runtime information

## 📜 Logging

The script logs information and errors to `azure_manager.log` in the same directory as the script.

## ⚠️ Caution

This script deletes Azure snapshots. Use with caution and ensure you have the necessary permissions and backups before running.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check [issues page](https://github.com/yourusername/azure-snapshot-manager/issues).

## 📄 License

This project is [MIT](https://choosealicense.com/licenses/mit/) licensed.

## 👏 Acknowledgements

- Thanks to the Azure CLI team for providing a robust command-line interface.
- Special thanks to the creators of the `rich` library for beautiful console output.

---

Happy snapshot managing! 🎉
