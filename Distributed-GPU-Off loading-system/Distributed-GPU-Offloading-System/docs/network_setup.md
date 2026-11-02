# Network Setup Guide

## Overview

This guide explains how to connect two Windows computers for a local LAN demonstration using either a direct CAT6 Ethernet cable or a shared Wi-Fi network.

---

## Option 1: Direct Ethernet Connection (Recommended for Demo)

### What you need
- One CAT6 (or CAT5e) Ethernet cable
- Two Windows 10/11 computers

### Step 1: Connect the Cable
Plug each end of the Ethernet cable directly into the Ethernet port of each computer. No router or switch is needed.

### Step 2: Configure Static IP Addresses

**On the SERVER computer:**

1. Open **Control Panel** → **Network and Sharing Center** → **Change adapter settings**
2. Right-click your **Ethernet** adapter → **Properties**
3. Select **Internet Protocol Version 4 (TCP/IPv4)** → **Properties**
4. Select **Use the following IP address:**

   | Field | Value |
   |-------|-------|
   | IP address | `192.168.1.1` |
   | Subnet mask | `255.255.255.0` |
   | Default gateway | (leave blank) |

5. Click **OK** on all dialogs.

**On the CLIENT computer:**

Same steps, but use:

| Field | Value |
|-------|-------|
| IP address | `192.168.1.2` |
| Subnet mask | `255.255.255.0` |
| Default gateway | (leave blank) |

> **Important:** These are example addresses. If your computers already have static IPs or are on another subnet, choose addresses that do not conflict with your existing network. Any two addresses in the same subnet work (e.g., `10.0.0.1` / `10.0.0.2`).

### Step 3: Verify Connectivity

Open **Command Prompt** on the client and run:

```cmd
ipconfig
```

Confirm the IPv4 Address shows `192.168.1.2`.

Then ping the server:

```cmd
ping 192.168.1.1
```

You should see replies. If not, check the firewall steps below.

---

## Option 2: Wi-Fi (Same Router)

Both computers must connect to the **same Wi-Fi network**.

### Find each computer's IP address:

Open **Command Prompt** and run:

```cmd
ipconfig
```

Look for the **Wireless LAN adapter Wi-Fi** section and note the **IPv4 Address** (e.g., `192.168.0.105`).

Repeat on the second computer to get its IP.

Enter the server computer's IP in the client application's **Server IP** field.

> For a stable demo, assign static IPs through your router's DHCP reservation feature to prevent IP changes.

---

## Step 4: Configure Windows Firewall

The server must allow inbound connections on port 8000.

**Run as Administrator on the SERVER computer:**

```powershell
New-NetFirewallRule -DisplayName "GPU Offload Server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

To verify the rule was created:

```powershell
Get-NetFirewallRule -DisplayName "GPU Offload Server"
```

To remove the rule after the demo:

```powershell
Remove-NetFirewallRule -DisplayName "GPU Offload Server"
```

---

## Step 5: Verify the Server is Listening

After starting the server, verify it is listening on the correct port:

```cmd
netstat -an | findstr 8000
```

You should see:

```
TCP    0.0.0.0:8000    0.0.0.0:0    LISTENING
```

Or from the client, open a browser and navigate to:

```
http://192.168.1.1:8000/health
```

You should see a JSON response with `"status": "online"`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ping` fails | Check firewall rules; verify IP addresses; check cable |
| "Connection refused" in client | Server not running, or wrong port |
| "Connection timed out" | Wrong IP address, or firewall blocking |
| Upload very slow | Normal on Wi-Fi; use Ethernet for best performance |
| NVENC not detected | Verify NVIDIA drivers are installed on the server |

---

## Security Note

This system uses plain HTTP and WebSocket traffic, which is suitable only for a **trusted local network demo**. For any production or public deployment:

- Replace HTTP with HTTPS using an SSL certificate
- Replace WS with WSS (WebSocket Secure)
- Change the default `auth_token` in `config.json`
- Use a reverse proxy such as Nginx with TLS termination
