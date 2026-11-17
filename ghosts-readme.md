# GHOSTS Server Setup Guide
## For use with Atom2 Cyber Range Manager

GHOSTS (General Human-Oriented Synthetic Teammates and Systems) is an NPC orchestration framework developed by Carnegie Mellon University's Software Engineering Institute (SEI). It simulates realistic user behavior on networked systems for cyber training exercises.

---

## Prerequisites

- Proxmox cluster with Atom2 already running
- Ubuntu Server 22.04 LTS ISO
- At least 8GB RAM and 40GB disk for the GHOSTS VM

---

## Step 1 — Create the GHOSTS VM in Proxmox

Create a new VM with the following specs:

| Setting | Value |
|---|---|
| OS | Ubuntu Server 22.04 LTS |
| CPU | 2-4 cores |
| RAM | 8GB minimum |
| Disk | 40GB minimum (64GB recommended) |
| Network | net0 → vmbr0 (management network only) |

> **Important:** GHOSTS only needs to be on the management network. Training VMs reach it via net0 (DHCP).

---

## Step 2 — Install Ubuntu Server

During installation:
- Set a static IP or note the DHCP address assigned
- Enable OpenSSH server
- Use LVM for disk partitioning (allows easy expansion later)

After installation, update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

---

## Step 3 — Expand disk if needed (LVM)

If you need to expand the disk after increasing it in Proxmox:

```bash
# Check current layout
lsblk

# Expand partition (usually sda3 for Ubuntu LVM)
sudo growpart /dev/sda 3

# Expand LVM physical volume
sudo pvresize /dev/sda3

# Expand logical volume to use all free space
sudo lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv

# Resize filesystem
sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv

# Verify
df -h
```

---

## Step 4 — Install Docker

```bash
sudo apt install -y docker.io docker-compose git curl nano
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 5 — Clone the GHOSTS Repository

```bash
cd ~
git clone https://github.com/cmu-sei/GHOSTS.git
cd GHOSTS/src/Ghosts.Api
```

---

## Step 6 — Configure Environment Variables

Check the API's database connection string to find the expected password:

```bash
cat ~/GHOSTS/src/Ghosts.Api/appsettings.json | grep -i "connection\|password\|postgres" -A 2
```

Create the `.env` file matching that password:

```bash
cat > ~/GHOSTS/src/Ghosts.Api/.env << 'EOF'
POSTGRES_PASSWORD=<your-password-from-appsettings>
WEB_API_URL=http://<ghosts-vm-ip>:5000/api
WEB_N8N_API_URL=http://<ghosts-vm-ip>:5678
WEB_GRAFANA_URL=http://<ghosts-vm-ip>:3000
N8N_OWNER_EMAIL=admin@ghosts.local
N8N_OWNER_PASSWORD=YourN8NPassword123!
EOF
```

> **Critical:** The `POSTGRES_PASSWORD` in `.env` must match the password in `appsettings.json` connection string exactly. If they don't match the API will fail to connect to the database.

> **Important:** `POSTGRES_PASSWORD` only takes effect on first initialization of the database volume. If you need to change it after the volume is created, change it directly in the database (see Troubleshooting section).

---

## Step 7 — Start GHOSTS

```bash
cd ~/GHOSTS/src/Ghosts.Api
docker compose up -d --build
```

This will take several minutes on first run as it builds the frontend from source.

Verify all containers are running:

```bash
docker compose ps
```

You should see these containers running:

| Container | Port | Purpose |
|---|---|---|
| ghosts-postgres | 5432 | PostgreSQL database |
| ghosts-api | 5000 | REST API |
| ghosts-frontend | 4200 | Web UI |
| ghosts-grafana | 3000 | Dashboards |
| ghosts-n8n | 5678 | Workflow automation |

---

## Step 8 — Verify the API

```bash
curl -v http://localhost:5000/swagger
```

You should get a 200 response. If you get a 500 with a password authentication error see the Troubleshooting section.

---

## Step 9 — Access the Web Interfaces

From any machine on the management network:

| Interface | URL | Purpose |
|---|---|---|
| GHOSTS Frontend | `http://<ghosts-vm-ip>:4200` | Manage machines, groups, timelines |
| GHOSTS API Swagger | `http://<ghosts-vm-ip>:5000/swagger` | API documentation |
| Grafana | `http://<ghosts-vm-ip>:3000` | Activity dashboards |
| n8n | `http://<ghosts-vm-ip>:5678` | Workflow automation |

> **Note:** Grafana has anonymous access enabled by default — no login required.

---

## Step 10 — Auto-start on Boot

Add GHOSTS to crontab so it starts automatically after a reboot:

```bash
crontab -e
```

Add this line:

```
@reboot cd ~/GHOSTS/src/Ghosts.Api && docker compose up -d
```

---

## Step 11 — Install GHOSTS Client on VM Templates

GHOSTS clients connect to the API server and simulate realistic user behavior. Install the appropriate client on your Proxmox VM templates:

### Universal Client (Linux)

```bash
# Download the latest Universal client
wget https://github.com/cmu-sei/GHOSTS/releases/latest/download/ghosts-universal-linux-x64.zip
unzip ghosts-universal-linux-x64.zip -d ~/ghosts-client

# Configure the client to point at your GHOSTS API server
nano ~/ghosts-client/config/application.json
```

Update the `ApiUrl` in `application.json`:

```json
{
  "ApiUrl": "http://<ghosts-vm-ip>:5000/api",
  ...
}
```

Run the client as a regular user (not root):

```bash
cd ~/ghosts-client
./ghosts
```

### systemd Service (runs on boot)

```bash
sudo nano /etc/systemd/system/ghosts-client.service
```

```ini
[Unit]
Description=GHOSTS NPC Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/home/<your-username>/ghosts-client
ExecStart=/home/<your-username>/ghosts-client/ghosts
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ghosts-client
sudo systemctl start ghosts-client
```

---

## Integration with Atom2

Add GHOSTS client installation to your Atom2 Ubuntu config script so every deployed VM automatically connects to the GHOSTS server.

Add these variables to your config script in Atom2:

| Key | Default | Description |
|---|---|---|
| `ghosts_api_url` | `http://<ghosts-vm-ip>:5000/api` | GHOSTS API endpoint |

Then add to the config script content:

```bash
# ── GHOSTS Client Setup ───────────────────────────────────────────────────────
log "Installing GHOSTS client..."
wget -q https://github.com/cmu-sei/GHOSTS/releases/latest/download/ghosts-universal-linux-x64.zip -O /tmp/ghosts.zip
unzip -q /tmp/ghosts.zip -d /opt/ghosts-client

# Configure API URL
sed -i 's|"ApiUrl":.*|"ApiUrl": "{{ ghosts_api_url }}",|' /opt/ghosts-client/config/application.json

# Install systemd service
cat > /etc/systemd/system/ghosts-client.service << 'SERVICE'
[Unit]
Description=GHOSTS NPC Client
After=network-online.target

[Service]
Type=simple
User=manager
WorkingDirectory=/opt/ghosts-client
ExecStart=/opt/ghosts-client/ghosts
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE

systemctl enable ghosts-client
systemctl start ghosts-client
log "GHOSTS client installed and started."
```

---

## Troubleshooting

### Password authentication failed

This happens when the PostgreSQL volume was initialized with a different password than what `appsettings.json` expects.

Fix by changing the password directly in the database:

```bash
# Connect as postgres superuser
docker exec -it ghosts-postgres psql -U postgres

# Reset the ghosts user password to match appsettings.json
ALTER USER ghosts WITH PASSWORD 'your-password-from-appsettings';
\q

# Restart the API
docker compose restart ghosts-api
```

### No space left on device during build

Expand the VM disk in Proxmox then follow Step 3 to grow the LVM partition.

### Containers not starting after reboot

```bash
cd ~/GHOSTS/src/Ghosts.Api
docker compose up -d
```

Or check logs:

```bash
docker compose logs ghosts-api
```

### Reset everything and start fresh

```bash
cd ~/GHOSTS/src/Ghosts.Api
docker compose down -v  # WARNING: deletes all data
docker compose up -d --build
```

---

## Architecture Overview

```
Management Network
├── Atom2 VM (Django + Docker)
│   └── Manages range deployments
│
├── GHOSTS Server VM (Ubuntu Server + Docker)
│   ├── ghosts-api (port 5000)
│   ├── ghosts-frontend (port 4200)
│   ├── ghosts-grafana (port 3000)
│   ├── ghosts-n8n (port 5678)
│   └── ghosts-postgres (port 5432)
│
└── Training VMs (cloned from templates)
    ├── net0 → management (DHCP, reaches GHOSTS + Atom2)
    ├── net1 → training network 1
    └── net2 → training network 2
        └── GHOSTS client running → connects to GHOSTS API
```

---

## References

- [GHOSTS GitHub Repository](https://github.com/cmu-sei/GHOSTS)
- [GHOSTS Documentation](https://cmu-sei.github.io/GHOSTS/)
- [GHOSTS Quick Start](https://cmu-sei.github.io/GHOSTS/quickstart/)
- [CMU SEI GHOSTS Page](https://www.sei.cmu.edu/library/ghosts-software-and-supporting-materials/)