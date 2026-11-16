#!/usr/bin/env bash
# Runs the real wickctl `update` branch against stub sudo, systemctl, git and install. No network, no sudo.
# Usage: bash bot/spot/deploy/wickctl_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
W=$HERE/wickctl
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/sudo" <<'S'
#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
while a[:1] == ["-u"]: a = a[2:]
os.execvp(a[0], a)
S
cat > "$T/bin/systemctl" <<'S'
#!/usr/bin/env bash
echo "systemctl $*" >> "$LOG"
[ "$1" = "is-active" ] && { echo "$WAS"; [ "$WAS" = active ] || [ "$WAS" = activating ]; exit; }
exit 0
S
cat > "$T/bin/git" <<'S'
#!/usr/bin/env bash
echo "git $*" >> "$LOG"
exit "${GIT_RC:-0}"
S
cat > "$T/bin/install" <<'S'
#!/usr/bin/env bash
echo "install $*" >> "$LOG"
S
chmod +x "$T"/bin/*
fail=0
check() {  # name was git_rc expected-sequence expected-message-fragment
  local name=$1 was=$2 rc=$3 want=$4 frag=$5 out seq
  export LOG=$T/log WAS=$was GIT_RC=$rc WICK_DIR=$T/repo; : > "$LOG"
  out=$(PATH=$T/bin:$PATH bash "$W" update 2>&1)
  seq=$(awk '$1=="systemctl"&&$2=="stop"{print "stop"} $1=="git"{print "pull"} $1=="install"{print "install"} $1=="systemctl"&&$2=="start"{print "start"}' "$LOG" | paste -sd' ')
  if [ "$seq" = "$want" ] && [[ "$out" == *"$frag"* ]]; then echo "PASS  $name: [$seq] \"$out\""
  else echo "FAIL  $name: got [$seq] \"$out\"; want [$want] containing \"$frag\""; fail=1; fi
}
check "1 active"                    active     0 "stop pull install start" "restarted"
check "2 activating"                activating 0 "stop pull install start" "restarted"
check "3 inactive"                  inactive   0 "stop pull install"       "stays stopped. Start it with: wickctl start"
check "4 failed"                    failed     0 "stop pull install"       "stays stopped"
check "5 pull fails, was active"    active     1 "stop pull start"         "pull failed"
check "6 pull fails, was inactive"  inactive   1 "stop pull"               "pull failed"
if bash -n "$W"; then echo "PASS  7 bash -n wickctl"; else echo "FAIL  7 bash -n wickctl"; fail=1; fi
# order-check while the service is active: one line, a non-zero exit, nothing run (no sudo, no python)
export LOG=$T/log WAS=active WICK_DIR=$T/repo; : > "$LOG"
out=$(PATH=$T/bin:$PATH bash "$W" order-check </dev/null 2>&1); rc=$?
if [ "$rc" != 0 ] && [ "$out" = "The bot is running: stop it first (wickctl stop), then run wickctl order-check." ] \
    && [ "$(cat "$LOG")" = "systemctl is-active --quiet wickbot" ]; then
  echo "PASS  8 order-check refuses while active: \"$out\""
else echo "FAIL  8 order-check while active: rc $rc, \"$out\", calls [$(paste -sd' ' "$LOG")]"; fail=1; fi
# order-path: the hold file in the live_spot folder; the service is never touched
M=$T/repo/live_spot/order_path_serial
S1="From its next start the bot uses the serial order path. A running bot keeps the path it started with: wickctl restart applies it now."
B1="The hold is removed. From its next start the bot uses the batch order path if the order check has passed on this server (wickctl status says which)."
U1="usage: wickctl order-path serial|batch"
op() { export LOG=$T/log WAS=active WICK_DIR=$T/repo; : > "$LOG"; out=$(PATH=$T/bin:$PATH bash "$W" order-path $* 2>&1); rc=$?; }
rm -rf "$T/repo"
op serial
if [ "$rc" = 0 ] && [ -e "$M" ] && [ "$out" = "$S1" ] && [ ! -s "$LOG" ]; then echo "PASS  9 order-path serial: made the folder and the file, printed its line"
else echo "FAIL  9 order-path serial: rc $rc \"$out\""; fail=1; fi
op
if [ "$rc" = 0 ] && [ "$out" = "$(printf 'held on the serial order path by hand\n%s' "$U1")" ] && [ ! -s "$LOG" ]; then echo "PASS  10 order-path alone, held: the state and the usage"
else echo "FAIL  10 order-path alone, held: rc $rc \"$out\""; fail=1; fi
op batch
if [ "$rc" = 0 ] && [ ! -e "$M" ] && [ "$out" = "$B1" ] && [ ! -s "$LOG" ]; then echo "PASS  11 order-path batch: removed the file, printed its line"
else echo "FAIL  11 order-path batch: rc $rc \"$out\""; fail=1; fi
op batch
if [ "$rc" = 0 ] && [ "$out" = "$B1" ] && [ ! -s "$LOG" ]; then echo "PASS  12 order-path batch with no file: no error"
else echo "FAIL  12 order-path batch with no file: rc $rc \"$out\""; fail=1; fi
op
if [ "$rc" = 0 ] && [ "$out" = "$(printf 'no hold: the order check decides (wickctl status says which)\n%s' "$U1")" ] && [ ! -s "$LOG" ]; then echo "PASS  13 order-path alone, no hold: the state and the usage"
else echo "FAIL  13 order-path alone, no hold: rc $rc \"$out\""; fail=1; fi
op nonsense
if [ "$rc" = 0 ] && [ ! -e "$M" ] && [[ "$out" == *"$U1" ]] && [ ! -s "$LOG" ]; then echo "PASS  14 order-path with another word: the state and the usage, nothing changed"
else echo "FAIL  14 order-path nonsense: rc $rc \"$out\""; fail=1; fi
mkdir -p "$T/repo/live_spot"
op serial
if [ -e "$M" ] && [ "$out" = "$S1" ] && [ ! -s "$LOG" ]; then echo "PASS  15 order-path serial with the folder already there"
else echo "FAIL  15 order-path serial, folder present: \"$out\""; fail=1; fi
[ "$fail" = 0 ] && echo "WICKCTL TEST PASSED" || { echo "WICKCTL TEST FAILED"; exit 1; }
