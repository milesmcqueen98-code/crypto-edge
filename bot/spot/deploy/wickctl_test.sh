#!/usr/bin/env bash
# Runs the real wickctl `update` branch against stub sudo, systemctl, git and install. No network, no sudo.
# Usage: bash bot/spot/deploy/wickctl_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
W=$HERE/wickctl
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/sudo" <<'S'
#!/usr/bin/env bash
while [ "${1:-}" = "-u" ]; do shift 2; done
exec "$@"
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
[ "$fail" = 0 ] && echo "WICKCTL TEST PASSED" || { echo "WICKCTL TEST FAILED"; exit 1; }
