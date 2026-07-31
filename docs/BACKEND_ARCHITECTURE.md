# Backend architecture

Decky loads `main.py`, which intentionally contains no application logic. It
only exposes the `Plugin` class from `fourdeus_backend.plugin`.

## Plugin boundary

`fourdeus_backend.plugin` owns process lifecycle and system-key orchestration.
Decky RPC methods are grouped by feature under
`fourdeus_backend/endpoints/`:

- `developer.py` — developer mode and diagnostics;
- `controller.py` — Controller module lifecycle and recovery operations;
- `nested_desktop.py` — Nested Desktop module lifecycle and RustDesk settings;
- `system_tools.py` — managed App Bridge, MangoHud, and SteamOS integrations.

Optional native and system integrations are isolated in `dependencies.py`.
Failure to import one integration does not prevent the keyboard or unrelated
tools from loading.

## Trackpads

The public `trackpad_metrics.py` module is a compatibility facade.
Implementation lives in `fourdeus_backend/trackpads/`:

- `controller.py` discovers and safely resets the built-in controller;
- `parsing.py` converts raw HID reports into immutable models;
- `monitor.py` owns the reader thread and sampling loop;
- `recovery.py` contains the anomaly/recovery state machine;
- `persistence.py` owns captures and the append-only rolling journal.

Recovery and metrics share the same HID stream, but persistence and controller
mutation remain outside the hot report parser.

The Controller master switch gates both automatic recovery and developer
metrics. Their saved child preferences are retained while the monitor is
stopped.

## Nested Desktop

The executable `nested_desktop_mouse.py` remains the stable worker path used by
the supervisor. Its implementation lives in
`fourdeus_backend/nested_desktop/`:

- `discovery.py` finds sessions and input devices;
- `touch.py` parses the Steam Deck's type-B multitouch stream;
- `rustdesk.py` handles RustDesk protocols and translation;
- `bindings.py` parses Steam Deck reports and applies bindings;
- `pointer_capture.py` captures the Gamescope XI2 master pointer without
  detaching physical devices;
- `gamescope.py`, `x11.py`, `cursor.py`, and `eis.py` wrap their respective
  native APIs;
- `clipboard.py` and `clipboard_x11.py` own event-driven X11 selection I/O,
  including chunked and `INCR` transfers;
- `clipboard_content.py` validates bounded text, image, and local file-URI
  payloads; `clipboard_bridge.py` synchronizes them without reading file
  contents or polling;
- `runtime_*.py` separate lifecycle, focus transitions, remote input, and HID
  ingestion;
- `supervisor.py` owns the worker subprocess and restart policy.

### User-space input driver and fallback contract

The Nested Desktop worker is deliberately a **user-space input driver/bridge**,
not a replacement kernel driver. Linux and SteamOS retain ownership of the
Steam Deck HID, evdev, XInput, and Gamescope devices. The worker reads the
interfaces those drivers already expose, applies focus and routing policy, and
injects the resulting events into Nested Desktop through KWin EIS.

When a Proton game is running behind Nested Desktop, two input paths cooperate:

1. The direct `hidraw` path decodes Steam Deck controls for low-latency
   trackpad motion, clicks, bindings, and inertia.
2. The Gamescope XI2 path captures its master pointer so mouse, trackpad,
   button, and scroll events cannot also reach the background game.
3. A short delayed queue deduplicates XI2 events that match recent direct HID
   activity. Events from an external USB or Bluetooth mouse remain intact and
   are forwarded through EIS.

Compatibility and graceful degradation are architectural requirements rather
than incidental behavior:

- With no parallel Proton game, the XI2 capture stays inactive and Gamescope's
  native input path remains unchanged.
- If XI2 capture is unavailable or already owned, the direct HID bridge,
  hotkeys, touchscreen, RustDesk, and unrelated modules keep working. Only
  background-game click isolation and external-pointer relay are degraded.
- If direct HID access is unavailable, the Gamescope path can still relay
  pointer input. Neither path is treated as an unconditional dependency of the
  other.
- If KWin EIS is unavailable, the worker never captures Gamescope input; native
  input remains usable instead of being consumed without a destination.
- Focus loss, Steam keyboard suspension, worker shutdown, and capture errors
  all ungrab the master pointer, synthesize releases for held buttons, and
  restore the Gamescope cursor.
- The Gamescope relay has its own persisted switch. Disabling it restores the
  native Gamescope behavior without disabling Nested Desktop hotkeys or the
  direct Steam Deck bridge.
- Settings written by older releases remain valid. Missing fields receive
  backward-compatible defaults in memory and are written only on the next
  normal settings update; no destructive migration is required.

This layering lets the plugin add driver-like behavior without patching the
kernel, replacing SteamOS device drivers, or making recovery depend on a device
reboot.

The Nested Desktop master switch is persisted separately from mouse, binding,
touchscreen, inertia, and RustDesk preferences. It stops the worker without
overwriting those child settings, then restores the same configuration when
re-enabled.

Clipboard sharing is independently gated and disabled by default. File and
folder sharing forwards only local `file://` references because Gamescope and
Nested Desktop use the same filesystem. It deliberately normalizes file-manager
cut metadata to copy semantics, so a cross-session paste cannot move or delete
the original. No file bytes are duplicated by the bridge.

The root supervisor opens the protected physical touchscreen without grabbing
it and passes only that file descriptor to the regular-user worker. The worker
waits on the descriptor with the rest of its event sources and forwards
multitouch frames through KWin EIS only while Nested Desktop owns input focus.
This keeps the idle path polling-free and leaves Steam's own touchscreen input
untouched outside Nested Desktop.

Touch inertia uses kernel event timestamps to estimate release velocity. It
arms only after a sufficiently long and directionally consistent
single-contact swipe. While active it alone lowers the event-loop deadline to
60 Hz, applies frame-time-corrected exponential decay, and releases the
synthetic contact after the final low-speed frame. Idle touch forwarding adds
no timer or polling loop.

The top-level compatibility facades preserve existing imports for tests,
installed wrappers, and external tooling.
