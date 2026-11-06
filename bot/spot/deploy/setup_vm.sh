#!/usr/bin/env bash
# One-time setup of an always-on Ubuntu 24.04 server (e.g. a $12-24/month DigitalOcean / Vultr / Lightsail VM in a US
# east region) for the live spot bot. Run as root:  bash setup_vm.sh
# Afterwards: fill in /etc/wickbot.env, run the preflight, then start the service (bot/spot/README.md, steps 5-7).
set -euo pipefail

apt-get update -y
apt-get install -y python3-venv python3-pip git chrony unattended-upgrades
systemctl enable --now chrony                           # accurate clock: the bot works on minute boundaries
timedatectl set-timezone UTC

id wick >/dev/null 2>&1 || useradd -m -s /bin/bash wick
sudo -u wick bash -lc '
  cd ~ && [ -d crypto-edge ] || git clone https://github.com/milesmcqueen98-code/crypto-edge.git
  cd crypto-edge && python3 -m venv .venv && . .venv/bin/activate &&
  pip install --upgrade pip && pip install pandas numpy lightgbm requests pyarrow coinbase-advanced-py &&
  mkdir -p live_spot &&
  [ -f bot/spot/config.live.json ] || cp bot/spot/config.json bot/spot/config.live.json'

if [ ! -f /etc/wickbot.env ]; then
  cp /home/wick/crypto-edge/bot/spot/deploy/wickbot.env.example /etc/wickbot.env
fi
chown root:wick /etc/wickbot.env && chmod 640 /etc/wickbot.env

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
systemctl enable wickbot-watchdog.timer

echo
echo "Server ready. Its public IP (put it in the API key's IP allowlist):"
curl -s https://api.ipify.org || true
echo
echo "Next: edit /etc/wickbot.env (keys), edit /home/wick/crypto-edge/bot/spot/config.live.json (capital,"
echo "coins_disabled), run the preflight, then: systemctl enable --now wickbot wickbot-watchdog.timer"
