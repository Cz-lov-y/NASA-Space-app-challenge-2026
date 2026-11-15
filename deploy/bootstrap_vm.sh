#!/usr/bin/env bash
# Configure the VM after /opt/earthrisk and /etc/earthrisk/*.env are installed.
set -euo pipefail

app_dir=/opt/earthrisk
host_name="${1:?Usage: bootstrap_vm.sh PUBLIC_HOST}"
if [[ ! "$host_name" =~ ^[a-zA-Z0-9.-]+$ ]]; then echo 'Invalid hostname' >&2; exit 1; fi
if [[ ! -f "$app_dir/deploy/gateway.py" ]] || ! sudo test -f /etc/earthrisk/gateway.env || ! sudo test -f /etc/earthrisk/provider.env; then
  echo 'Application and private environment files must be installed first.' >&2; exit 1
fi
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip caddy rsync
if ! id earthrisk >/dev/null 2>&1; then sudo useradd --system --home-dir "$app_dir" --shell /usr/sbin/nologin earthrisk; fi
sudo chown -R earthrisk:earthrisk "$app_dir"
sudo chown root:earthrisk /etc/earthrisk /etc/earthrisk/gateway.env /etc/earthrisk/provider.env
sudo chmod 0750 /etc/earthrisk
sudo chmod 0640 /etc/earthrisk/gateway.env /etc/earthrisk/provider.env
sudo -u earthrisk python3 -m venv "$app_dir/.venv"
sudo -u earthrisk "$app_dir/.venv/bin/pip" install -q -r "$app_dir/requirements-data.txt" -r "$app_dir/requirements-earthengine.txt"
sudo tee /etc/systemd/system/earthrisk-api.service >/dev/null <<UNIT
[Unit]
Description=EarthRisk local API
After=network-online.target
Wants=network-online.target
[Service]
User=earthrisk
Group=earthrisk
WorkingDirectory=$app_dir
Environment=EARTH_ENGINE_PROJECT=tactical-attic-456217-t0
ExecStart=$app_dir/.venv/bin/python scripts/serve_regional_api.py --port 8000 --env-file /etc/earthrisk/provider.env --enable-live
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/earthrisk-gateway.service >/dev/null <<UNIT
[Unit]
Description=EarthRisk authenticated gateway
After=network-online.target earthrisk-api.service
Wants=network-online.target
[Service]
User=earthrisk
Group=earthrisk
WorkingDirectory=$app_dir
EnvironmentFile=/etc/earthrisk/gateway.env
ExecStart=$app_dir/.venv/bin/python deploy/gateway.py
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/earthrisk-worker.service >/dev/null <<UNIT
[Unit]
Description=EarthRisk Earth Engine acquisition
After=network-online.target
Wants=network-online.target
[Service]
User=earthrisk
Group=earthrisk
WorkingDirectory=$app_dir
Environment=PYTHONUNBUFFERED=1
ExecStart=$app_dir/.venv/bin/python scripts/global_screen_earth_engine.py --project tactical-attic-456217-t0 --priority-canada-prairies --fetch --request-workers 4 --min-free-gib 20
Restart=on-failure
RestartSec=20
[Install]
WantedBy=multi-user.target
UNIT
# The gateway trusts X-Real-IP only from this loopback reverse proxy.
sudo tee /etc/caddy/Caddyfile >/dev/null <<CADDY
$host_name {
    reverse_proxy 127.0.0.1:8081 {
        header_up X-Real-IP {remote_host}
    }
    header Strict-Transport-Security "max-age=31536000"
}
CADDY
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now earthrisk-api earthrisk-gateway
sudo systemctl restart caddy
# The caller starts earthrisk-worker only after the local writer stops and the
# final complete-release snapshot has been transferred and verified.
