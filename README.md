# 🚀 Veltrix Cloud — Pterodactyl Manager Bot

A professional Discord bot for managing a Pterodactyl hosting panel directly from Discord.

The bot connects to your Pterodactyl Panel through the **Application API** and allows administrators to create and manage panel users, create/delete servers, view nodes, eggs, servers and account information.

It also provides private customer commands for viewing their own account and servers.

---

## ✨ Features

- 👤 Create Pterodactyl users from Discord
- 🔗 Automatically link Discord users with Pterodactyl accounts
- 📧 Store customer email and username mapping
- 🔐 Generate secure Pterodactyl passwords
- 📩 Send account credentials to the customer through Discord DM
- 🖥️ Create Pterodactyl servers from Discord
- 🌐 Live Pterodactyl node information
- 🥚 Live Nest and Egg information
- 📦 Automatic free allocation selection
- 💾 Automatic Egg environment handling
- 🗑️ Delete Pterodactyl servers
- 👥 View linked customers
- 🔎 View server information
- 📋 Customers can view their own servers
- 🔑 Private credential viewing
- 📊 Node information
- 📚 `/help` command for customers
- 💬 Discord embeds
- 🔒 Private customer information
- 🗄️ SQLite database
- ⚡ Async API requests
- 🔄 Automatic systemd restart
- 24/7 operation
- 🛡️ Admin-only management commands

---

# 📋 Requirements

You need:

- Ubuntu 22.04 / 24.04 recommended
- Python 3.10+
- A Discord Bot
- A Discord Server
- A Pterodactyl Panel
- Pterodactyl Application API Key
- Root access to the Linux server running the bot

Example panel:

`https://panel.veltrixcloud.online`

---

# 🤖 Discord Bot Setup

Open:

https://discord.com/developers/applications

Create a new Discord Application.

Then:

1. Open **Bot**
2. Click **Add Bot**
3. Reset/Copy the bot token
4. Enable the required intents
5. Open **OAuth2 → URL Generator**
6. Select:

### Scopes

```text
bot
applications.commands
Bot Permissions
View Channels
Send Messages
Embed Links
Read Message History
Invite the generated bot URL to your Discord server.
🔑 Pterodactyl API Setup
Login to your Pterodactyl administrator account.
Go to:
Admin Panel
→ Application API
→ Create New
Create an Application API key.
Copy the API key into .env.
The API key must have permission to perform the operations required by the bot.
Never publish the API key publicly.
📁 Installation
Clone or upload this repository to your server.
Recommended directory:
/opt/veltrix-ptero-manager
Create the directory:
sudo mkdir -p /opt/veltrix-ptero-manager
cd /opt/veltrix-ptero-manager
🐍 Install Python
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
Create the virtual environment:
python3 -m venv venv
Activate it:
source venv/bin/activate
Install dependencies:
pip install -r requirements.txt
⚙️ Configure .env
Create the environment file:
cp .env.example .env
Edit it:
nano .env
Example:
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
CLIENT_ID=YOUR_DISCORD_APPLICATION_ID
GUILD_ID=YOUR_DISCORD_SERVER_ID
ADMIN_ID=YOUR_DISCORD_USER_ID

PTERODACTYL_URL=https://panel.veltrixcloud.online
PTERODACTYL_API_KEY=YOUR_PTERODACTYL_APPLICATION_API_KEY

DATABASE_PATH=/opt/veltrix-ptero-manager/data.db
Configuration
Variable
Description
DISCORD_TOKEN
Discord bot token
CLIENT_ID
Discord application/client ID
GUILD_ID
Discord server ID
ADMIN_ID
Main administrator Discord ID
PTERODACTYL_URL
Pterodactyl panel URL
PTERODACTYL_API_KEY
Pterodactyl Application API key
DATABASE_PATH
SQLite database location
🗄️ Database
The bot uses SQLite.
Default database:
/opt/veltrix-ptero-manager/data.db
The database stores the Discord ↔ Pterodactyl account mapping.
Example information:
Discord ID
Pterodactyl User ID
Pterodactyl Email
Pterodactyl Username
Pterodactyl Password
The database is automatically created when the bot starts.
▶️ Run the Bot
Activate the virtual environment:
cd /opt/veltrix-ptero-manager
source venv/bin/activate
Check the Python file:
python3 -m py_compile bot.py
Start the bot:
python3 bot.py
A successful startup should show the Discord bot connecting and synchronizing commands.
🔄 24/7 Systemd Setup
Create the service:
sudo nano /etc/systemd/system/veltrix-ptero-manager.service
Paste:
[Unit]
Description=Veltrix Cloud Pterodactyl Manager Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/veltrix-ptero-manager
ExecStart=/opt/veltrix-ptero-manager/venv/bin/python3 /opt/veltrix-ptero-manager/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
Save the file.
Reload systemd:
sudo systemctl daemon-reload
Enable the service:
sudo systemctl enable veltrix-ptero-manager
Start:
sudo systemctl start veltrix-ptero-manager
Check:
sudo systemctl status veltrix-ptero-manager --no-pager
View live logs:
sudo journalctl -u veltrix-ptero-manager -f
Restart:
sudo systemctl restart veltrix-ptero-manager
Stop:
sudo systemctl stop veltrix-ptero-manager
👤 User Commands
These commands are available to normal customers.
/help
Shows the available customer commands.
/help
The help menu does not expose administrator commands.
/panel
Shows the Pterodactyl panel link.
/panel
/manage
Shows the customer's linked Pterodactyl account.
/manage
Information can include:
Pterodactyl Username
Pterodactyl Email
Pterodactyl User ID
Panel
/user-info
Shows the customer's linked Pterodactyl account information.
/user-info
/credentials
Privately displays the customer's Pterodactyl credentials.
/credentials
Credentials are sent privately and should not be exposed in public channels.
/my-server-list
Shows servers belonging to the logged-in customer.
/my-server-list
/server-info
Shows information about a customer's server.
/server-info
Only servers belonging to the linked customer should be accessible through the customer command.
!my-server
Prefix command for quickly viewing the customer's servers.
!my-server
For this command, Message Content Intent must be enabled in the Discord Developer Portal.
👑 Administrator Commands
The following commands are intended for administrators.
They are not displayed in the normal /help customer menu.
/user-create
Creates a new Pterodactyl account and links it to a Discord member.
Example flow:
/user-create
→ Select Discord Member
→ Enter Email
→ Enter Username
→ Create Pterodactyl User
→ Link Discord account
→ Send credentials by DM
The customer receives their account information privately.
/user-list
Lists linked Pterodactyl customers.
/user-list
/user-info
Administrator account-management information can be accessed according to the bot's administrator permissions.
/user-delete
Deletes a linked Pterodactyl user.
/user-delete
This is an administrator operation.
🖥️ Server Management
/server-create
Creates a Pterodactyl server.
The server creation process uses the Pterodactyl API.
Typical flow:
/server-create
        ↓
Select Discord Customer
        ↓
Customer / Pterodactyl account
        ↓
Select available Node
        ↓
Enter Server Name
        ↓
Select/enter RAM
        ↓
Select/enter CPU
        ↓
Select/enter Disk
        ↓
Select Nest / Egg
        ↓
Find available allocation
        ↓
Create Server
The bot obtains live information from Pterodactyl instead of relying on hardcoded nodes.
🌐 Node Selection
The bot can request live node information from Pterodactyl.
Example information:
Node ID
Node Name
Location
FQDN
Memory
Disk
Allocations
Available allocations can be checked before creating a server.
The bot can automatically select an available allocation.
🥚 Nest & Egg
Pterodactyl Eggs are obtained from the panel API.
The bot can retrieve:
Nest
Egg
Docker Image
Startup Command
Environment Variables
Egg-specific environment variables are required when Pterodactyl requires them.
For example:
SERVER_JARFILE
BUILD_NUMBER
The server creation process should use the values provided by the selected Egg.
📦 Server Resources
Server resources are configured through Pterodactyl.
Typical limits:
RAM
CPU
Disk
Swap
IO
Databases
Allocations
Backups
The actual available resources depend on the selected Pterodactyl node.
📩 Server Creation Notification
After successful server creation:
Admin
The administrator receives a Discord embed containing server information.
Example:
Server Created

Server Name
Server ID
Customer
Node
Allocation
RAM
CPU
Disk
Customer
The selected customer receives a private Discord DM containing the server information.
🗑️ /server-delete
Deletes a Pterodactyl server.
/server-delete
Administrator permission is required.
📋 /server-list
Administrator server listing.
/server-list
This command is intended for administrators.
🌐 /nodes
Displays Pterodactyl node information.
/nodes
Node information is retrieved live from the Pterodactyl API.
🛠️ /admin
Administrator management interface.
/admin
Available administrator operations can include:
Node List
Server List
Sync
🔐 Security
The bot is designed so that sensitive information is not unnecessarily exposed.
Customer credentials
Passwords should only be displayed privately.
Discord mapping
Each linked customer can be associated with:
Discord ID
Pterodactyl User ID
Email
Username
API key
Never place the Pterodactyl API key inside:
README.md
GitHub source code
Discord messages
Public screenshots
Keep it inside:
.env
and never commit .env to GitHub.
🚫 .gitignore
Create a .gitignore file:
.env
*.db
__pycache__/
*.pyc
venv/
This prevents secrets, databases and virtual-environment files from being uploaded accidentally.
🔎 Testing
Check syntax:
python3 -m py_compile bot.py
Check service:
systemctl status veltrix-ptero-manager --no-pager
Check logs:
journalctl -u veltrix-ptero-manager -n 100 --no-pager
Follow live logs:
journalctl -u veltrix-ptero-manager -f
🩺 Troubleshooting
Bot keeps restarting
Run:
journalctl -u veltrix-ptero-manager -n 100 --no-pager
Look for the Python traceback.
CommandAlreadyRegistered
This means two commands have the same Discord slash-command name.
Check:
grep -n '@bot.tree.command' bot.py
Make sure every command name is unique.
For example:
server-list
my-server-list
must not both be registered as:
server-list
/help does not appear
Restart the bot:
systemctl restart veltrix-ptero-manager
Then check:
journalctl -u veltrix-ptero-manager -n 50 --no-pager
Make sure the bot successfully synchronizes commands.
!my-server does not work
Enable:
Message Content Intent
in:
Discord Developer Portal
→ Your Application
→ Bot
→ Privileged Gateway Intents
→ Message Content Intent
Then restart the bot.
Pterodactyl API error
Check:
PTERODACTYL_URL
PTERODACTYL_API_KEY
in .env.
Then restart:
systemctl restart veltrix-ptero-manager
HTTP 422 during server creation
A Pterodactyl 422 ValidationException normally means one or more required server fields are missing or invalid.
Check the selected Egg's required environment variables.
Common examples:
SERVER_JARFILE
BUILD_NUMBER
Use the Egg's actual configuration instead of hardcoding values that the Egg does not support.
📊 Architecture
Discord
   │
   ▼
Veltrix Cloud Discord Bot
   │
   ├── Discord Commands
   │
   ├── SQLite Database
   │
   └── Pterodactyl Application API
              │
              ▼
       Pterodactyl Panel
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
     Node    Node    Node
       │
       ├── Servers
       ├── Allocations
       ├── Nests
       └── Eggs
📁 Project Structure
veltrix-ptero-manager/
│
├── bot.py
├── requirements.txt
├── .env
├── .env.example
├── data.db
├── venv/
│
└── __pycache__/
📦 Dependencies
The bot uses:
discord.py
aiohttp
aiosqlite
python-dotenv
Install:
pip install -r requirements.txt
🔄 Updating the Bot
Before updating:
systemctl stop veltrix-ptero-manager
Backup the existing bot:
cp /opt/veltrix-ptero-manager/bot.py /opt/veltrix-ptero-manager/bot.py.backup
Replace the updated bot.py.
Check syntax:
/opt/veltrix-ptero-manager/venv/bin/python3 -m py_compile /opt/veltrix-ptero-manager/bot.py
Start again:
systemctl start veltrix-ptero-manager
Check:
systemctl status veltrix-ptero-manager --no-pager
⚡ Quick Commands
Start
systemctl start veltrix-ptero-manager
Stop
systemctl stop veltrix-ptero-manager
Restart
systemctl restart veltrix-ptero-manager
Status
systemctl status veltrix-ptero-manager --no-pager
Logs
journalctl -u veltrix-ptero-manager -f
Syntax check
python3 -m py_compile bot.py
🌩️ Veltrix Cloud
Veltrix Cloud — Pterodactyl Manager
Manage your hosting infrastructure directly from Discord.
Discord
   ↓
Veltrix Cloud Manager
   ↓
Pterodactyl Panel
   ↓
Nodes
   ↓
Servers
📜 License
For personal/internal hosting-community use.
