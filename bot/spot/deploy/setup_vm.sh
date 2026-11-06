#!/usr/bin/env bash
# One-time setup of an always-on Ubuntu 24.04 server (a ~$12/month 2 GB AWS Lightsail instance in us-east-1, or similar)
# for the live spot bot. Run:  sudo bash setup_vm.sh
# Then: sudo wickctl configure, wickctl paper-test, wickctl preflight, wickctl start (bot/spot/README.md).
set -euo pipefail

apt-get update -y
apt-get install -y python3-venv python3-pip git chrony unattended-upgrades
systemctl enable --now chrony                           # accurate clock: the bot works on minute boundaries
timedatectl set-timezone UTC

id wick >/dev/null 2>&1 || useradd -m -s /bin/bash wick
sudo -u wick bash -lc '
  # only the code the bot needs (~50 MB, not the 1.8 GB of research data)
  cd ~ && [ -d crypto-edge ] || { git clone --depth 1 --filter=blob:none --sparse https://github.com/milesmcqueen98-code/crypto-edge.git &&
    git -C crypto-edge sparse-checkout set bot edge reports; }
  cd crypto-edge && python3 -m venv .venv && . .venv/bin/activate &&
  pip install --upgrade pip && pip install pandas numpy lightgbm requests pyarrow coinbase-advanced-py &&
  mkdir -p live_spot &&
  [ -f bot/spot/config.live.json ] || python3 -c "import json; c = json.load(open(\"bot/spot/config.json\")); c[\"capital\"] = 0; json.dump(c, open(\"bot/spot/config.live.json\", \"w\"), indent=2)"'

# secrets file: filled in by `sudo wickctl configure`; live trading stays off until you say yes there
if [ ! -f /etc/wickbot.env ]; then
  printf '# Filled in by: sudo wickctl configure\nI_UNDERSTAND_LIVE_TRADING=no\n' > /etc/wickbot.env
fi
chown root:wick /etc/wickbot.env && chmod 640 /etc/wickbot.env

install -m 755 /home/wick/crypto-edge/bot/spot/deploy/wickctl /usr/local/bin/wickctl
cp /home/wick/crypto-edge/bot/spot/deploy/wickbot.service /etc/systemd/system/wickbot.service
cat > /etc/systemd/system/wickbot-watchdog.service <<'EOF'
[Unit]
Description=Wick bot watchdog (alerts)
[Service]
Type=oneshot
User=wick
WorkingDirectory=/home/wick/crypto-edge
EnvironmentFile=/etc/wickbot.env
ExecStart=/home/wick/crypto-edge/.venv/bin/python bot/spot/deploy/watchdog.py live_spot
EOF
cat > /etc/systemd/system/wickbot-watchdog.timer <<'EOF'
[Unit]
Description=Run the wick bot watchdog every 5 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload

echo
echo "Server ready. This server's public IP (it goes in the API key's IP allowlist):"
curl -s https://api.ipify.org || true
echo
echo "Next: sudo wickctl configure   (then: wickctl paper-test, wickctl preflight, wickctl start)"
