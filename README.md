# 🌟 Azure Snapshot Management Tool v4 🌟

Efficiently manage your Azure snapshots across multiple subscriptions with this powerful and user-friendly Python script! 🚀

## 🌈 Features

- 📊 Inventory snapshots across multiple subscriptions
- 🗑️ Delete snapshots based on a provided list
- 📈 Real-time progress tracking with estimated time remaining
- 🎨 Beautiful console output using Rich
- 📝 Detailed logging for auditing and troubleshooting
- 🔍 Automatic resource group detection for each snapshot

## 🚀 Quick Start

1. Ensure you have Python 3.7+ installed
2. Install required packages:
   ```
   pip install azure-cli rich
   ```
3. Run the script:
   ```
   python v4-snapmgr.py
   ```
4. Follow the prompts to select an action and provide the snapshot list file

## 🔧 Configuration

- Snapshot list file: A text file containing one snapshot name per line
- Logs are saved in 'snapshot_management.log'

## 🎛️ Actions

1. **Inventory**: 
   - Creates a CSV file with details of all snapshots
   - Output: 'snapshots_inventory.csv'

2. **Delete**:
   - Deletes snapshots listed in the provided file
   - Automatically detects the resource group for each snapshot
   - Displays real-time progress and total deleted count

## 📊 Progress Tracking

- 🔄 Live progress bar showing overall completion percentage
- ⏱️ Estimated time remaining for the entire operation
- 🔢 Current subscription and snapshot being processed

## 🚨 Error Handling

- ❗ Errors are displayed in the console in bold red text
- 📝 All errors are logged to 'snapshot_management.log' for further analysis
- 🔍 Detailed error messages for issues like missing resource groups

## 🔐 Safety First!

Always double-check your snapshot list before running the delete action. This script performs irreversible deletions! ⚠️

## 🌈 Future Enhancements

- 🌐 Multi-region support
- 📊 Advanced analytics and reporting
- 🔐 Enhanced security features
- 🔄 Automatic retry for failed operations
- 📅 Scheduled runs for regular maintenance

## 🤝 Contributing

We welcome contributions! Feel free to open issues or submit PRs to help make this script even more awesome! 🎉

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

💡 "In the cloud, every snapshot tells a story. Make sure yours has a happy ending!" - Azure Snapshot Sage