# 🚀 Awesome Azure Snapshot Creator 📸

## 🌟 Introduction

Welcome to the Awesome Azure Snapshot Creator! This powerful Python script automates the process of creating snapshots for your Azure VMs, making your life easier and your infrastructure more secure. 🛡️

## 🎯 Features

- 🔥 Blazing fast snapshot creation
- 📊 Real-time progress bar
- 📝 Detailed logging
- 📈 Summary report generation
- 🕰️ Automatic expiration check for old snapshots
- 🎨 Beautiful console output

## 🛠️ Prerequisites

Before you begin, ensure you have the following:

- Python 3.6+
- Azure CLI
- Rich library (`pip install rich`)

## 🚀 Quick Start

1. Clone this repository:
   ```
   git clone https://github.com/rsuar29/awesome-azure-snapshot-creator.git
   ```

2. Navigate to the project directory:
   ```
   cd azure-snapshot
   ```

3. Install required packages:
   ```
   pip install -r requirements.txt
   ```

4. Create a `snapshot_vmlist.txt` file with your VM resource IDs and names:
   ```
   /subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/virtualMachines/vm1 vm1
   /subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/virtualMachines/vm2 vm2
   ```

5. Run the script:
   ```
   python v5-create-snap-promax.py
   ```

6. Sit back and watch the magic happen! ✨

## 📊 Output

The script provides:

- 🖥️ Console output with a progress bar and success messages
- 📄 Detailed log file (`snapshot_log_TIMESTAMP.txt`)
- 📑 Summary report (`snapshot_summary_TIMESTAMP.txt`)

## 🤝 Contributing

Contributions make the open-source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📞 Contact

Your Name - [@yourtwitter](https://twitter.com/yourtwitter) - email@example.com

Project Link: [https://github.com/yourusername/awesome-azure-snapshot-creator](https://github.com/yourusername/awesome-azure-snapshot-creator)

## 🙏 Acknowledgments

- [Rich library](https://github.com/Textualize/rich) for the beautiful console output
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/) for seamless Azure integration
- ☕ Coffee for fueling late-night coding sessions

---

Made with ❤️ and 🐍
