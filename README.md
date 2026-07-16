# facecast

Mirror your Linux desktop onto your face: streams your screen (and audio) to a
phone in a Google Cardboard headset, rendered side-by-side with lens-distortion
correction. Plug the phone in over USB for low-latency wired streaming.

## How it works

- `facecast` (the launcher) makes sure the streaming server is running, opens
  the sender page in your browser, waits for USB tethering to come up, and
  opens the viewer page on the phone (automatically via `adb` if available,
  otherwise it prints the URL and a QR code).
- The **sender page** captures your display via `getDisplayMedia` (works on
  Wayland through the xdg-desktop-portal screen picker) and your desktop audio
  via a PipeWire/PulseAudio *monitor* device, then streams both over WebRTC.
- The **viewer page** on the phone renders the stream twice through a WebGL
  barrel-distortion shader, cancelling the Cardboard lenses' pincushion
  distortion. Tap the screen for controls: image size, eye distance, and lens
  curve, all persisted per device.
- Media is pinned to whichever network path the phone dialed — over USB
  tethering that means the video rides the cable even while the phone's Wi-Fi
  is on. The launcher also stops the tethering link from hijacking your PC's
  default route.
- The tiny Python server (stdlib only, port 8765) serves the two pages and
  relays the WebRTC handshake. Video flows peer-to-peer, not through it.

Latency over the cable is roughly 50–90 ms glass-to-glass — fine for desktop
use, video, and casual games; don't expect to win at anything twitchy.

## Install

From the AUR:

```
yay -S facecast        # or paru, or makepkg -si from a clone
```

Then enable the server and run the launcher:

```
systemctl --user enable --now facecast.service
facecast
```

Manual install: clone the repo and run `./start.sh` — it starts the server
itself if the systemd unit isn't installed.

## Usage

1. Plug the phone in over USB. With `adb` set up (USB debugging enabled), the
   launcher enables tethering and opens the viewer on the phone by itself;
   otherwise enable **USB tethering** on the phone and scan the QR code.
2. On the PC: click **Share screen**, pick your display, and when the
   microphone prompt appears pick the **"Monitor of …"** device (that's your
   desktop audio, not your mic). Check "remember" to skip it next time.
3. On the phone: tap once for fullscreen + audio, slot it into the headset,
   and use the tap-menu to fine-tune size / eye distance / lens curve.

Keep the phone's Wi-Fi **on** even when wired — Android won't route its own
browser to the tethering subnet without an active network. The video still
uses the cable.

## Firewall

The handshake uses TCP 8765 and WebRTC media uses ephemeral UDP ports. With
firewalld:

```
sudo firewall-cmd --permanent --add-port=8765/tcp --add-port=32768-60999/udp
sudo firewall-cmd --reload
```

Anyone on your LAN who can reach these ports can watch your screen while
you're sharing — there is no authentication. Share on networks you trust.

## Tips

- Each eye only gets about half the phone's panel: bump your desktop scaling
  (or lower the resolution) so text survives the trip.
- Subpixel (RGB) font antialiasing turns into rainbow fringing on video —
  switch your font antialiasing to grayscale for a much cleaner picture.
- Sessions are single-viewer: a second phone opening the viewer page steals
  the stream from the first.

## Disclaimer

🤖 This project was vibe coded with Claude (Fable 5) — a human chose what to
build and verified it works; the AI wrote the code. Read it before you run it,
as you should with any stranger's screen-streaming server.

## License

MIT
