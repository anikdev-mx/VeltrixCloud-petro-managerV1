import os
import asyncio
import logging
import secrets
import string
from typing import Optional

import aiohttp
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
GUILD_ID = os.getenv("GUILD_ID", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
PTERODACTYL_URL = os.getenv("PTERODACTYL_URL", "").rstrip("/")
PTERODACTYL_API_KEY = os.getenv("PTERODACTYL_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/opt/veltrix-ptero-manager/data.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("veltrix")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class PteroAPI:
    def __init__(self, base_url: str, key: str):
        self.base = base_url.rstrip("/")
        self.key = key

    async def request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self.key}",
            "Accept": "Application/vnd.pterodactyl.v1+json",
            "Content-Type": "application/json",
        })
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.request(method, self.base + path, **kwargs) as r:
                text = await r.text()
                if r.status >= 400:
                    raise RuntimeError(f"Pterodactyl HTTP {r.status}: {text[:500]}")
                return await r.json() if text else {}

    async def nodes(self):
        out, page = [], 1
        while True:
            data = await self.request("GET", f"/api/application/nodes?page={page}")
            out.extend(data.get("data", []))
            last = data.get("meta", {}).get("pagination", {}).get("current_page", page)
            total = data.get("meta", {}).get("pagination", {}).get("total_pages", last)
            if last >= total:
                return out
            page += 1

    async def node(self, node_id):
        return await self.request("GET", f"/api/application/nodes/{node_id}?include=allocations")

    async def eggs(self, nest_id):
        return await self.request("GET", f"/api/application/nests/{nest_id}/eggs?include=variables")

    async def nests(self):
        out, page = [], 1
        while True:
            data = await self.request("GET", f"/api/application/nests?page={page}")
            out.extend(data.get("data", []))
            p = data.get("meta", {}).get("pagination", {})
            if p.get("current_page", page) >= p.get("total_pages", page):
                return out
            page += 1

    async def users(self, email: Optional[str] = None):
        path = "/api/application/users"
        if email:
            path += "?filter[email]=" + aiohttp.helpers.quote(email)
        return await self.request("GET", path)

    async def create_user(self, email, username, first, last, password=None):
        body = {"email": email, "username": username, "first_name": first, "last_name": last}
        if password:
            body["password"] = password
        return await self.request("POST", "/api/application/users", json=body)

    async def servers(self):
        out, page = [], 1
        while True:
            data = await self.request("GET", f"/api/application/servers?page={page}")
            out.extend(data.get("data", []))
            p = data.get("meta", {}).get("pagination", {})
            if p.get("current_page", page) >= p.get("total_pages", page):
                return out
            page += 1

    async def create_server(self, payload):
        return await self.request("POST", "/api/application/servers", json=payload)

    async def server_action(self, server_id, action):
        # Application API endpoint for power actions is not available on all Pterodactyl versions.
        # Use the client API for user-facing power actions in a production build.
        raise RuntimeError("Use the Client API for power actions; this starter bot focuses on admin Application API.")

    async def delete_server(self, server_id, force=False):
        suffix = "?force=true" if force else ""
        return await self.request("DELETE", f"/api/application/servers/{server_id}{suffix}")


ptero = PteroAPI(PTERODACTYL_URL, PTERODACTYL_API_KEY)


async def db():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    con = await aiosqlite.connect(DATABASE_PATH)
    await con.execute("""CREATE TABLE IF NOT EXISTS links (
        discord_id INTEGER PRIMARY KEY,
        ptero_user_id INTEGER NOT NULL,
        ptero_email TEXT,
        ptero_username TEXT,
        ptero_password TEXT
    )""")
    columns = {row[1] for row in await con.execute_fetchall("PRAGMA table_info(links)")}
    if "ptero_username" not in columns:
        await con.execute("ALTER TABLE links ADD COLUMN ptero_username TEXT")
    if "ptero_password" not in columns:
        await con.execute("ALTER TABLE links ADD COLUMN ptero_password TEXT")
    await con.commit()
    return con


def generate_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-"
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*_-"),
    ]
    chars += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


async def get_link(discord_id):
    con = await db()
    try:
        cur = await con.execute(
            "SELECT discord_id,ptero_user_id,ptero_email,ptero_username,ptero_password "
            "FROM links WHERE discord_id=?", (discord_id,)
        )
        return await cur.fetchone()
    finally:
        await con.close()


async def save_link(discord_id, ptero_user_id, email, username, password):
    con = await db()
    try:
        await con.execute(
            """INSERT INTO links(discord_id,ptero_user_id,ptero_email,ptero_username,ptero_password)
               VALUES(?,?,?,?,?)
               ON CONFLICT(discord_id) DO UPDATE SET
               ptero_user_id=excluded.ptero_user_id,
               ptero_email=excluded.ptero_email,
               ptero_username=excluded.ptero_username,
               ptero_password=excluded.ptero_password""",
            (discord_id, ptero_user_id, email, username, password),
        )
        await con.commit()
    finally:
        await con.close()


async def delete_link(discord_id):
    con = await db()
    try:
        await con.execute("DELETE FROM links WHERE discord_id=?", (discord_id,))
        await con.commit()
    finally:
        await con.close()


def credential_embed(member, email, username, password):
    embed = discord.Embed(
        title="🔐 Veltrix Cloud • Pterodactyl Account",
        description=f"Your Pterodactyl account has been created for {member.mention}.",
    )
    embed.add_field(name="🌐 Panel", value=PTERODACTYL_URL or "Not configured", inline=False)
    embed.add_field(name="📧 Email", value=f"`{email}`", inline=False)
    embed.add_field(name="👤 Username", value=f"`{username}`", inline=False)
    embed.add_field(name="🔑 Password", value=f"||`{password}`||", inline=False)
    embed.set_footer(text="Keep these credentials private • Veltrix Cloud")
    return embed



def is_admin(interaction: discord.Interaction) -> bool:
    return ADMIN_ID and interaction.user.id == ADMIN_ID


async def require_admin(interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return False
    return True


def obj(item):
    return item.get("attributes", item)


class NodeSelect(discord.ui.Select):
    def __init__(self, nodes):
        options = []
        for n in nodes[:25]:
            a = obj(n)
            options.append(discord.SelectOption(
                label=f"{a.get('name','Node')} (#{a.get('id')})"[:100],
                value=str(a.get("id")),
                description=f"{a.get('fqdn','')}"[:100]
            ))
        super().__init__(placeholder="Select a Pterodactyl node", options=options)


class NodeView(discord.ui.View):
    def __init__(self, nodes):
        super().__init__(timeout=60)
        self.add_item(NodeSelect(nodes))


@bot.event
async def on_ready():
    await db()
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", GUILD_ID)
        else:
            await bot.tree.sync()
            log.info("Synced global commands")
    except Exception:
        log.exception("Command sync failed")
    log.info("Logged in as %s", bot.user)


@bot.tree.command(name="panel", description="Open the Veltrix Pterodactyl panel")
async def panel(interaction: discord.Interaction):
    if not PTERODACTYL_URL:
        return await interaction.response.send_message("Panel URL is not configured.", ephemeral=True)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Open Panel", style=discord.ButtonStyle.link, url=PTERODACTYL_URL))
    await interaction.response.send_message("🔐 **Veltrix Cloud Panel**", view=view, ephemeral=True)


@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)} ms`", ephemeral=True)


@bot.tree.command(name="admin")
@app_commands.describe(action="Admin action")
@app_commands.choices(action=[
    app_commands.Choice(name="node-list", value="node-list"),
    app_commands.Choice(name="server-list", value="server-list"),
    app_commands.Choice(name="sync", value="sync"),
])
async def admin(interaction: discord.Interaction, action: app_commands.Choice[str]):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        if action.value == "node-list":
            nodes = await ptero.nodes()
            lines = [f"🖥️ **{obj(n).get('name')}** — ID `{obj(n).get('id')}` — `{obj(n).get('fqdn','')}`" for n in nodes]
            await interaction.followup.send("\n".join(lines)[:1900] or "No nodes found.", ephemeral=True)
        elif action.value == "server-list":
            servers = await ptero.servers()
            lines = [f"🎮 **{obj(s).get('name')}** — ID `{obj(s).get('id')}`" for s in servers]
            await interaction.followup.send("\n".join(lines)[:1900] or "No servers found.", ephemeral=True)
        else:
            await interaction.followup.send("✅ Pterodactyl connection/config is loaded.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


@bot.tree.command(name="nodes", description="Show live Pterodactyl nodes (admin)")
async def nodes(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        ns = await ptero.nodes()
        embed = discord.Embed(title="🖥️ Pterodactyl Nodes", description="\n".join(
            f"`#{obj(n).get('id')}` **{obj(n).get('name')}** • {obj(n).get('fqdn','')}" for n in ns
        )[:4000])
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


class EmailModal(discord.ui.Modal, title="Server Creation • Customer Email"):
    email = discord.ui.TextInput(label="Customer Email", placeholder="customer@example.com", required=True, max_length=191)

    def __init__(self, admin_interaction, member):
        super().__init__()
        self.admin_interaction = admin_interaction
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await ptero.users(str(self.email.value).strip())
            rows = result.get("data", [])
            if not rows:
                await interaction.followup.send(embed=discord.Embed(title="❌ User Not Found", description="No Pterodactyl user exists with that email."), ephemeral=True)
                return
            if len(rows) > 1:
                await interaction.followup.send(embed=discord.Embed(title="❌ Multiple Users Found", description="More than one Pterodactyl user matched this email."), ephemeral=True)
                return
            ptero_user = obj(rows[0])
            view = await make_node_view(self.member, ptero_user, str(self.email.value).strip())
            embed = discord.Embed(title="🖥️ Server Create • Step 2/5", description="Select the **Pterodactyl node** where this server will be created.")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=f"`{e}`"), ephemeral=True)


class EmailButtonView(discord.ui.View):
    def __init__(self, member):
        super().__init__(timeout=300)
        self.member = member

    @discord.ui.button(label="Enter Customer Email", style=discord.ButtonStyle.primary, emoji="📧")
    async def email_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        await interaction.response.send_modal(EmailModal(interaction, self.member))


class NodeSelectWizard(discord.ui.Select):
    def __init__(self, nodes, member, ptero_user, email):
        self.member = member
        self.ptero_user = ptero_user
        self.email = email
        options = []
        for n in nodes[:25]:
            a = obj(n)
            options.append(discord.SelectOption(label=f"{a.get('name','Node')} (#{a.get('id')})"[:100], value=str(a.get('id')), description=str(a.get('fqdn',''))[:100]))
        super().__init__(placeholder="Select available node", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            node_id = int(self.values[0])
            node = obj(await ptero.node(node_id))
            allocs = node.get("relationships", {}).get("allocations", {}).get("data", [])
            free = [obj(x) for x in allocs if not obj(x).get("assigned")]
            if not free:
                await interaction.followup.send(embed=discord.Embed(title="❌ No Available Allocation", description="This node has no free allocation/port available."), ephemeral=True)
                return
            view = AllocationWizardView(self.member, self.ptero_user, self.email, node, free)
            embed = discord.Embed(title="🌐 Server Create • Step 3/5", description="Select an **available allocation / port**. Only free allocations are shown.")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Node Error", description=f"`{e}`"), ephemeral=True)


class NodeWizardView(discord.ui.View):
    def __init__(self, member, ptero_user, email):
        super().__init__(timeout=300)
        self.add_item(NodeSelectWizard(self._nodes_placeholder(), member, ptero_user, email))

    def _nodes_placeholder(self):
        return []


# NodeWizardView loads the live nodes before displaying the select.
async def make_node_view(member, ptero_user, email):
    nodes = await ptero.nodes()
    view = discord.ui.View(timeout=300)
    view.add_item(NodeSelectWizard(nodes, member, ptero_user, email))
    return view


class AllocationSelectWizard(discord.ui.Select):
    def __init__(self, member, ptero_user, email, node, allocations):
        self.member = member
        self.ptero_user = ptero_user
        self.email = email
        self.node = node
        self.allocations = allocations
        options = []
        for a in allocations[:25]:
            ip = a.get("ip_alias") or a.get("ip") or "IP"
            port = a.get("port", "?")
            options.append(discord.SelectOption(label=f"{ip}:{port}"[:100], value=str(a.get("id")), description=f"Allocation #{a.get('id')}"[:100]))
        super().__init__(placeholder="Select available allocation", options=options)

    async def callback(self, interaction: discord.Interaction):
        allocation = next(a for a in self.allocations if str(a.get("id")) == self.values[0])
        embed = discord.Embed(title="⚙️ Server Create • Step 4/5", description="Enter the server name and resources. RAM/Disk are in GB and CPU is in %. ")
        view = ResourceModalView(self.member, self.ptero_user, self.email, self.node, allocation)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AllocationWizardView(discord.ui.View):
    def __init__(self, member, ptero_user, email, node, allocations):
        super().__init__(timeout=300)
        self.add_item(AllocationSelectWizard(member, ptero_user, email, node, allocations))


class ResourceModal(discord.ui.Modal, title="Server Resources"):
    name = discord.ui.TextInput(label="Server Name", placeholder="My Minecraft Server", required=True, max_length=100)
    ram = discord.ui.TextInput(label="RAM (GB)", placeholder="4", required=True, max_length=6)
    cpu = discord.ui.TextInput(label="CPU (%)", placeholder="100", required=True, max_length=6)
    disk = discord.ui.TextInput(label="Disk (GB)", placeholder="20", required=True, max_length=8)

    def __init__(self, member, ptero_user, email, node, allocation):
        super().__init__()
        self.member, self.ptero_user, self.email, self.node, self.allocation = member, ptero_user, email, node, allocation

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ram_gb = float(self.ram.value)
            cpu = int(self.cpu.value)
            disk_gb = float(self.disk.value)
            if ram_gb <= 0 or disk_gb <= 0 or cpu <= 0:
                raise ValueError("RAM, CPU and Disk must be greater than 0.")
            memory = int(ram_gb * 1024)
            disk = int(disk_gb * 1024)
            if cpu > 10000:
                raise ValueError("CPU cannot exceed 10000%.")
            nests = await ptero.nests()
            if not nests:
                raise RuntimeError("No Pterodactyl nests are available.")
            view = NestWizardView(self.member, self.ptero_user, self.email, self.node, self.allocation, self.name.value.strip(), memory, cpu, disk, nests)
            embed = discord.Embed(title="🥚 Server Create • Step 5/5", description="Select the **Nest**, then select its Egg. The final server will be created automatically.")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid Resources", description=f"`{e}`"), ephemeral=True)


class ResourceModalView(discord.ui.View):
    def __init__(self, member, ptero_user, email, node, allocation):
        super().__init__(timeout=300)
        self.member, self.ptero_user, self.email, self.node, self.allocation = member, ptero_user, email, node, allocation

    @discord.ui.button(label="Enter Server Resources", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ResourceModal(self.member, self.ptero_user, self.email, self.node, self.allocation))


class NestSelectWizard(discord.ui.Select):
    def __init__(self, member, ptero_user, email, node, allocation, name, memory, cpu, disk, nests):
        self.member, self.ptero_user, self.email = member, ptero_user, email
        self.node, self.allocation = node, allocation
        self.name, self.memory, self.cpu, self.disk = name, memory, cpu, disk
        self.nests = nests
        options = [discord.SelectOption(label=f"{obj(n).get('name','Nest')} (#{obj(n).get('id')})"[:100], value=str(obj(n).get('id'))) for n in nests[:25]]
        super().__init__(placeholder="Select server type / Nest", options=options)

    async def callback(self, interaction: discord.Interaction):
        nest_id = int(self.values[0])
        eggs = (await ptero.eggs(nest_id)).get("data", [])
        if not eggs:
            await interaction.response.send_message(embed=discord.Embed(title="❌ No Eggs", description="No eggs were found in this nest."), ephemeral=True)
            return
        view = EggWizardView(self.member, self.ptero_user, self.email, self.node, self.allocation, self.name, self.memory, self.cpu, self.disk, nest_id, eggs)
        await interaction.response.send_message(embed=discord.Embed(title="🥚 Select Egg", description="Choose the exact Egg for this server."), view=view, ephemeral=True)


class NestWizardView(discord.ui.View):
    def __init__(self, *args):
        super().__init__(timeout=300)
        self.add_item(NestSelectWizard(*args))


class EggSelectWizard(discord.ui.Select):
    def __init__(self, member, ptero_user, email, node, allocation, name, memory, cpu, disk, nest_id, eggs):
        self.member, self.ptero_user, self.email = member, ptero_user, email
        self.node, self.allocation = node, allocation
        self.name, self.memory, self.cpu, self.disk = name, memory, cpu, disk
        self.nest_id, self.eggs = nest_id, eggs
        options = []
        for e in eggs[:25]:
            a = obj(e)
            options.append(discord.SelectOption(label=f"{a.get('name','Egg')} (#{a.get('id')})"[:100], value=str(a.get('id')), description=str(a.get('description',''))[:100]))
        super().__init__(placeholder="Select Egg", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            egg_id = int(self.values[0])
            egg = next(obj(e) for e in self.eggs if int(obj(e).get("id", 0)) == egg_id)
            # Build the environment from the selected Egg's variables.
            # Pterodactyl validates required Egg variables during server creation;
            # sending an empty environment causes 422 errors such as
            # SERVER_JARFILE / BUILD_NUMBER being required.
            environment = {}
            variables = egg.get("relationships", {}).get("variables", {}).get("data", [])
            for variable in variables:
                va = obj(variable)
                key = va.get("env_variable") or va.get("key")
                if not key:
                    continue
                value = va.get("default_value")
                if value is None:
                    value = va.get("default")
                if value is None:
                    value = ""
                environment[key] = str(value)

            # Common Minecraft/Paper/Forge egg defaults. These are used only
            # when the Egg exposes the variables without usable defaults.
            if "SERVER_JARFILE" in environment and not environment["SERVER_JARFILE"]:
                environment["SERVER_JARFILE"] = "server.jar"
            if "BUILD_NUMBER" in environment and not environment["BUILD_NUMBER"]:
                environment["BUILD_NUMBER"] = "latest"

            payload = {
                "name": self.name,
                "user": int(obj(self.ptero_user).get("id")),
                "nest": self.nest_id,
                "egg": egg_id,
                "docker_image": egg.get("docker_image") or "ghcr.io/pterodactyl/yolks:java_21",
                "startup": egg.get("startup") or "",
                "environment": environment,
                "limits": {"memory": self.memory, "swap": 0, "disk": self.disk, "io": 500, "cpu": self.cpu, "threads": None, "oom_disabled": False},
                "feature_limits": {"databases": 0, "allocations": 1, "backups": 2},
                "deploy": {"locations": [], "port_range": [], "dedicated_ip": False},
                "allocation": {"default": int(self.allocation.get("id"))},
            }
            created = obj(await ptero.create_server(payload))
            server_id = created.get("id")
            identifier = created.get("identifier", "N/A")
            ip = self.allocation.get("ip_alias") or self.allocation.get("ip") or "N/A"
            port = self.allocation.get("port", "N/A")
            node_name = self.node.get("name", "Node")
            embed = discord.Embed(title="🎉 Veltrix Cloud • Server Created", description="Your server has been created successfully and is ready to manage.")
            embed.add_field(name="🎮 Server", value=f"`{self.name}`", inline=True)
            embed.add_field(name="🆔 Server ID", value=f"`{server_id}`", inline=True)
            embed.add_field(name="🔑 Identifier", value=f"`{identifier}`", inline=True)
            embed.add_field(name="👤 Owner", value=self.member.mention, inline=True)
            embed.add_field(name="📧 Email", value=f"`{self.email}`", inline=True)
            embed.add_field(name="🖥️ Node", value=f"`{node_name}`", inline=True)
            embed.add_field(name="🌐 Address", value=f"`{ip}:{port}`", inline=False)
            embed.add_field(name="🧠 RAM", value=f"`{self.memory // 1024} GB`", inline=True)
            embed.add_field(name="💻 CPU", value=f"`{self.cpu}%`", inline=True)
            embed.add_field(name="💾 Disk", value=f"`{self.disk // 1024} GB`", inline=True)
            embed.set_footer(text="Veltrix Cloud • Server provisioning • 24/7 management")
            view = discord.ui.View(timeout=None)
            if PTERODACTYL_URL:
                view.add_item(discord.ui.Button(label="🌐 Open Panel", style=discord.ButtonStyle.link, url=PTERODACTYL_URL))
            # Permanent channel message: not ephemeral and does not auto-delete.
            await interaction.channel.send(content=self.member.mention, embed=embed, view=view)
            try:
                await self.member.send(embed=embed, view=view)
                dm = "Customer DM sent."
            except discord.Forbidden:
                dm = "⚠️ Customer DMs are disabled; channel message was posted."
            await interaction.followup.send(embed=discord.Embed(title="✅ Server Setup Complete", description=f"Server `{self.name}` was created. {dm}"), ephemeral=True)
        except Exception as e:
            log.exception("server-create wizard failed")
            await interaction.followup.send(embed=discord.Embed(title="❌ Server Creation Failed", description=f"`{e}`"), ephemeral=True)


class EggWizardView(discord.ui.View):
    def __init__(self, *args):
        super().__init__(timeout=300)
        self.add_item(EggSelectWizard(*args))


@bot.tree.command(name="server-create", description="Create a Pterodactyl server using a guided setup (admin)")
@app_commands.describe(discord_user="Discord customer who will own the server")
async def server_create(interaction: discord.Interaction, discord_user: discord.Member):
    if not await require_admin(interaction):
        return
    try:
        view = EmailButtonView(discord_user)
        embed = discord.Embed(title="🛠️ Veltrix Cloud • Server Create • Step 1/5", description=f"Customer: {discord_user.mention}\n\nClick below and enter the customer's **Pterodactyl email**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(title="❌ Error", description=f"`{e}`"), ephemeral=True)

@bot.tree.command(name="server-delete", description="Delete a Pterodactyl server (admin)")
@app_commands.describe(server_id="Pterodactyl server ID")
async def server_delete(interaction: discord.Interaction, server_id: int):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await ptero.delete_server(server_id, force=True)
        await interaction.followup.send(f"🗑️ Server `{server_id}` deleted.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


@bot.tree.command(name="server-list", description="List Pterodactyl servers (admin)")
async def server_list(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        ss = await ptero.servers()
        lines = []
        for s in ss:
            a = obj(s)
            lines.append(f"`#{a.get('id')}` **{a.get('name')}** • owner `{a.get('user')}`")
        await interaction.followup.send("\n".join(lines)[:1900] or "No servers.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


@bot.tree.command(name="user-create", description="Create a Pterodactyl account for a Discord member (admin)")
@app_commands.describe(
    member="Discord member who receives the credentials",
    email="Pterodactyl account email",
    username="Pterodactyl username",
)
async def user_create(interaction: discord.Interaction, member: discord.Member, email: str, username: str):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    password = generate_password()
    try:
        display = (member.display_name or member.name).strip()
        first = "".join(c for c in display if c.isalnum() or c in " _-").strip() or "Veltrix"
        result = await ptero.create_user(email, username, first[:191], "Cloud", password)
        a = obj(result)
        ptero_id = int(a["id"])

        await save_link(member.id, ptero_id, email, username, password)

        try:
            await member.send(embed=credential_embed(member, email, username, password))
            dm_status = "Credentials were sent privately to the selected member."
        except discord.Forbidden:
            dm_status = "⚠️ DMs are disabled. Password was NOT exposed in this channel."

        embed = discord.Embed(
            title="✅ Pterodactyl User Created",
            description=dm_status,
        )
        embed.add_field(name="Discord", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Pterodactyl ID", value=f"`{ptero_id}`", inline=True)
        embed.add_field(name="Username", value=f"`{username}`", inline=True)
        embed.add_field(name="Email", value=f"`{email}`", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        log.exception("user-create failed")
        await interaction.followup.send(
            embed=discord.Embed(title="❌ User Creation Failed", description=f"`{e}`"),
            ephemeral=True,
        )


@bot.tree.command(name="credentials", description="View private Pterodactyl credentials")
@app_commands.describe(member="Admin only: another linked Discord member")
async def credentials(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    if member is not None and not is_admin(interaction):
        await interaction.response.send_message("❌ Only the admin can request another member's credentials.", ephemeral=True)
        return
    target = member or interaction.user
    row = await get_link(target.id)
    if not row:
        await interaction.response.send_message("❌ No linked Pterodactyl account found.", ephemeral=True)
        return
    _, ptero_id, email, username, password = row
    if not password:
        await interaction.response.send_message("❌ No stored password is available.", ephemeral=True)
        return
    m = target if isinstance(target, discord.Member) else interaction.user
    embed = credential_embed(m, email, username, password)
    embed.add_field(name="Pterodactyl ID", value=f"`{ptero_id}`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="manage", description="Open your private Veltrix Cloud manager")
async def manage(interaction: discord.Interaction):
    row = await get_link(interaction.user.id)
    if not row:
        await interaction.response.send_message("❌ Your Discord account is not linked.", ephemeral=True)
        return
    _, ptero_id, email, username, _ = row
    embed = discord.Embed(
        title="🛠️ Veltrix Cloud • Manage",
        description=f"**Username:** `{username}`\n**Email:** `{email}`\n**Pterodactyl ID:** `{ptero_id}`",
    )
    view = discord.ui.View(timeout=120)
    view.add_item(discord.ui.Button(label="🌐 Open Panel", style=discord.ButtonStyle.link, url=PTERODACTYL_URL))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="my-server-list", description="Show your own Pterodactyl servers privately")
async def customer_server_list(interaction: discord.Interaction):
    row = await get_link(interaction.user.id)
    if not row:
        await interaction.response.send_message("❌ Your Discord account is not linked.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        owner_id = int(row[1])
        servers = await ptero.servers()
        owned = [obj(s) for s in servers if int(obj(s).get("user", 0) or 0) == owner_id]
        embed = discord.Embed(title="🖥️ Your Servers")
        if not owned:
            embed.description = "No servers found."
        else:
            for a in owned[:25]:
                embed.add_field(
                    name=f"🎮 {a.get('name','Unnamed')}",
                    value=f"ID: `{a.get('id')}` • Identifier: `{a.get('identifier','N/A')}`",
                    inline=False,
                )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=f"`{e}`"), ephemeral=True)


@bot.tree.command(name="server-info", description="Show your own server information privately")
@app_commands.describe(server_id="Pterodactyl server ID")
async def customer_server_info(interaction: discord.Interaction, server_id: int):
    row = await get_link(interaction.user.id)
    if not row:
        await interaction.response.send_message("❌ Your Discord account is not linked.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        owner_id = int(row[1])
        servers = await ptero.servers()
        found = next((obj(s) for s in servers if int(obj(s).get("id", 0)) == server_id), None)
        if not found or int(found.get("user", 0) or 0) != owner_id:
            await interaction.followup.send("❌ That server is not linked to your account.", ephemeral=True)
            return
        embed = discord.Embed(title=f"🖥️ {found.get('name','Server')}")
        embed.add_field(name="Server ID", value=f"`{found.get('id')}`", inline=True)
        embed.add_field(name="Identifier", value=f"`{found.get('identifier','N/A')}`", inline=True)
        embed.add_field(name="Owner", value=f"`{owner_id}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=f"`{e}`"), ephemeral=True)


@bot.tree.command(name="user-list", description="List linked Pterodactyl users (admin)")
async def user_list(interaction: discord.Interaction):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    con = await db()
    try:
        cur = await con.execute("SELECT discord_id,ptero_user_id,ptero_email,ptero_username FROM links ORDER BY discord_id")
        rows = await cur.fetchall()
    finally:
        await con.close()
    embed = discord.Embed(title="👥 Linked Users")
    if not rows:
        embed.description = "No linked users."
    for discord_id, ptero_id, email, username in rows[:25]:
        embed.add_field(
            name=f"Discord ID `{discord_id}`",
            value=f"Ptero `{ptero_id}` • `{username or 'N/A'}` • `{email or 'N/A'}`",
            inline=False,
        )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="user-info", description="Show your linked Pterodactyl account")
async def user_info(interaction: discord.Interaction):
    row = await get_link(interaction.user.id)
    if not row:
        await interaction.response.send_message("❌ Your Discord account is not linked.", ephemeral=True)
        return
    _, ptero_id, email, username, _ = row
    embed = discord.Embed(title="👤 Your Veltrix Cloud Account")
    embed.add_field(name="Pterodactyl ID", value=f"`{ptero_id}`", inline=True)
    embed.add_field(name="Username", value=f"`{username}`", inline=True)
    embed.add_field(name="Email", value=f"`{email}`", inline=False)
    embed.set_footer(text="Password is only shown through /credentials.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="user-delete", description="Delete a linked Pterodactyl user (admin)")
@app_commands.describe(member="Discord member")
async def user_delete(interaction: discord.Interaction, member: discord.Member):
    if not await require_admin(interaction):
        return
    row = await get_link(member.id)
    if not row:
        await interaction.response.send_message("❌ No linked account found.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await ptero.request("DELETE", f"/api/application/users/{int(row[1])}")
        await delete_link(member.id)
        await interaction.followup.send(embed=discord.Embed(
            title="🗑️ User Deleted",
            description=f"{member.mention}'s Pterodactyl account and Discord mapping were removed."
        ), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=f"`{e}`"), ephemeral=True)





@bot.tree.command(name="help", description="Show all available user commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 Veltrix Cloud • Help",
        description="Commands available to regular users.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="👤 Account",
        value=(
            "`/panel` — Open the Pterodactyl panel\n"
            "`/manage` — Open your private manager\n"
            "`/user-info` — View your linked account\n"
            "`/credentials` — Privately view your credentials"
        ),
        inline=False,
    )
    embed.add_field(
        name="🖥️ Servers",
        value=(
            "`/my-server-list` — View your servers\n"
            "`/server-info` — View server information\n"
            "`!my-server` — Quick server list"
        ),
        inline=False,
    )
    embed.set_footer(text="Veltrix Cloud • Pterodactyl Manager")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="my-server")
async def my_server_prefix(ctx):
    row = await get_link(ctx.author.id)
    if not row:
        return await ctx.send(embed=discord.Embed(title="❌ Not Linked", description="Your Discord account is not linked to a Pterodactyl account."))
    try:
        owner_id = int(row[1])
        servers = await ptero.servers()
        owned = [obj(s) for s in servers if int(obj(s).get("user", 0) or 0) == owner_id]
        embed = discord.Embed(title="🖥️ Your Servers", color=discord.Color.blurple())
        if not owned:
            embed.description = "No servers found."
        else:
            for server in owned[:25]:
                a = obj(server)
                embed.add_field(name=f"🎮 {a.get('name', 'Server')}", value=f"ID: `{a.get('id')}`\nIdentifier: `{a.get('identifier', 'N/A')}`", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(embed=discord.Embed(title="❌ Error", description=f"`{str(e)[:1800]}`", color=discord.Color.red()))


if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN is missing in .env")
if not PTERODACTYL_URL or not PTERODACTYL_API_KEY:
    raise SystemExit("PTERODACTYL_URL/PTERODACTYL_API_KEY is missing in .env")

asyncio.run(bot.start(DISCORD_TOKEN))
