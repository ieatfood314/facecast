#!/usr/bin/env bash
# facecast one-shot launcher:
#   plug the phone in, run this, follow at most two prompts.
set -u
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
[ -f "$DIR/server.py" ] || DIR=/usr/share/facecast
PORT=8765
BASE="http://localhost:$PORT"

say() { printf '\033[1;36m>>\033[0m %s\n' "$*"; }

# ---- 1. make sure the server is up (systemd unit preferred) ----------------
if ! curl -sf -m 2 "$BASE/status" >/dev/null; then
    systemctl --user start facecast.service 2>/dev/null \
        || { nohup python3 "$DIR/server.py" >/tmp/facecast.log 2>&1 & }
    for i in 1 2 3 4 5; do
        curl -sf -m 2 "$BASE/status" >/dev/null && break
        sleep 1
    done
fi
curl -sf -m 2 "$BASE/status" >/dev/null || { echo "server failed to start"; exit 1; }
say "server running on port $PORT"

# ---- 2. open the sender page unless a sender is already sharing ------------
if [ "$(curl -sf "$BASE/status" | grep -o '"sender": *true')" ]; then
    say "sender already sharing — leaving it alone"
else
    xdg-open "$BASE/" >/dev/null 2>&1 &
    say "opened sender page — click 'Share screen', pick your display,"
    say "then pick 'Monitor of …' in the microphone prompt"
fi

# ---- 3. find (or coax up) the USB tethering interface -----------------------
find_iface() {
    for d in /sys/class/net/*; do
        drv=$(basename "$(readlink -f "$d/device/driver" 2>/dev/null)" 2>/dev/null)
        case "$drv" in
            rndis_host|cdc_ncm|cdc_ether|cdc_eem) basename "$d"; return 0;;
        esac
    done
    return 1
}

adb_ok() { command -v adb >/dev/null && [ "$(adb get-state 2>/dev/null)" = "device" ]; }

iface=$(find_iface || true)
if [ -z "${iface:-}" ] && adb_ok; then
    say "asking the phone to enable USB tethering (adb)…"
    adb shell svc usb setFunctions rndis,adb 2>/dev/null \
        || adb shell svc usb setFunctions rndis 2>/dev/null || true
fi

say "waiting for USB tethering (plug in the phone / enable tethering)…"
ip=""
for i in $(seq 1 120); do
    iface=$(find_iface || true)
    if [ -n "${iface:-}" ]; then
        ip=$(ip -4 -o addr show "$iface" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
        [ -n "$ip" ] && break
    fi
    sleep 1
done
[ -n "$ip" ] || { echo "no tethering interface after 2 min — giving up"; exit 1; }
say "wired link up: $iface ($ip)"

# ---- 4. keep the phone from hijacking the default route --------------------
con=$(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null \
      | awk -F: -v d="$iface" '$2==d{print $1}')
if [ -n "$con" ] && [ "$(nmcli -t -f ipv4.never-default connection show "$con" | cut -d: -f2)" != "yes" ]; then
    nmcli connection modify "$con" ipv4.never-default yes ipv6.never-default yes \
        && nmcli device reapply "$iface" >/dev/null \
        && say "fixed default route (internet stays on Wi-Fi)"
fi

# ---- 5. get the viewer URL onto the phone -----------------------------------
url="http://$ip:$PORT/vr.html"
say "viewer URL: $url"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "$url"
if adb_ok && adb shell am start -a android.intent.action.VIEW -d "$url" >/dev/null 2>&1; then
    say "opened it on the phone via adb — tap once for fullscreen/audio"
else
    say "scan the QR (or type the URL) on the phone"
fi

say "done. leave this window; Ctrl-C won't kill the stream."
