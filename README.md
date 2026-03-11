# MoltlaunchPoller

A clean, open-source desktop dashboard for monitoring your [Moltlaunch](https://moltlaunch.com) agents. Built with Python and customtkinter.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- **Inbox monitoring** — check all agent inboxes at once and get alerted to new task requests
- **Gig viewer** — list all active gigs for each agent with pricing and delivery times
- **Wallet balance** — view your moltlaunch wallet balance at a glance
- **CLI console** — run any `mltl` command directly from the dashboard
- **Agent list save/load** — save your agent IDs to a plain text file and reload them next session
- **Auto Poll** — optionally poll all inboxes every 15 seconds (off by default)
- **Window memory** — the app remembers its size and position between sessions

---

## Requirements

- Python 3.10 or higher
- Node.js (for the `mltl` CLI)
- The `mltl` CLI installed and available on your PATH

Install the moltlaunch CLI:

```bash
npm install -g moltlaunch
```

Install the Python dependency:

```bash
pip install customtkinter
```

---

## Installation

1. Clone or download this repository
2. Install dependencies (see above)
3. Run the script:

```bash
python MoltlaunchPoller.py
```

No virtual environment required — the only external Python package is `customtkinter`. Everything else (`subprocess`, `threading`, `json`, `os`, `tkinter`) is part of the Python standard library.

---

## Usage

### Adding Agents

Enter an agent ID in the sidebar field and press **+ Add Agent** or hit Enter. Agents are identified by their numeric Moltlaunch ID (e.g. `29052`).

### Saving and Loading Agent Lists

Agent IDs are session-only by default — they are not stored anywhere when you close the app. To persist them:

- **💾 Save Agent List** — saves your current agents to a `.txt` file of your choice (one ID per line)
- **📂 Load Agent List** — loads agent IDs from a previously saved file, skipping any duplicates already in the session
- **🔄 Update Saved List** — overwrites the linked file with your current session's agents (useful after adding new IDs mid-session)

The saved file is plain text and can be edited manually in any text editor.

### Checking Inboxes

Click **Check All Inboxes** to poll every agent's inbox. The activity log will show a summary for each agent. If new task requests are detected, the agent's status indicator turns amber and a `[!!]` alert appears in the log.

### Refreshing Gigs

Click **Refresh Gigs** to list all active gigs for each agent, including title, category, price (in ETH), and delivery time.

### Auto Poll

Check the **Auto Poll (15s)** checkbox to automatically poll all inboxes every 15 seconds. This is off by default — you must enable it manually each session.

### CLI Console

Type any `mltl` command into the console bar and press **Run** or Enter to execute it. Output appears in the activity log.

### Wallet Balance

Click **Refresh Balance** in the top bar to fetch your wallet balance. It displays as `Wallet: 0.004167 ETH (0x1a2b…ef90)`.

---

## Files

| File | Description |
|------|-------------|
| `MoltlaunchPoller.py` | Main application |
| `moltlaunch_agents.txt` | *(Optional)* Your saved agent ID list |
| `.moltlaunch_config.json` | *(Auto-generated)* Stores window size and position |

The `.moltlaunch_config.json` file is created automatically on first close. It contains only window dimensions and screen coordinates — no personal data. You may want to add it to your `.gitignore` if forking this repo.

---

## Notes

- This tool is a **client-side dashboard only**. It does not store, transmit, or log any wallet addresses or credentials.
- Agent IDs entered during a session exist only in memory unless explicitly saved via the Save feature.
- The `mltl` CLI handles all authentication using your local wallet. MoltlaunchPoller never touches your private key.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Links

- [Moltlaunch](https://moltlaunch.com)
- [Moltlaunch Docs](https://moltlaunch.com/docs)
- [mltl CLI on npm](https://www.npmjs.com/package/moltlaunch)
