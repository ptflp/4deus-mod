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
- `clipboard.py`, `clipboard_owner.py`, and `clipboard_x11.py` own
  event-driven X11 selection observation, ownership, and low-level I/O,
  including chunked and `INCR` transfers;
- `clipboard_content.py` validates bounded text, image, and local file-URI
  payloads; `clipboard_klipper.py` observes native Wayland copy events through
  Klipper; `clipboard_bridge.py` synchronizes them without polling;
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
the original. A source application's portal token is ownership-scoped and is
never replayed. For sandboxed destinations, the bridge opens the selected
regular files or directories without reading them, registers their descriptors
in its own `org.freedesktop.portal.FileTransfer` session, and publishes the new
bounded `application/vnd.portal.filetransfer` token alongside the URI list.
The receiving application obtains access through the desktop portal. The
session is retired when clipboard ownership changes or the bridge closes.
Disabling file sharing removes both URI and portal formats.

Gamescope's XWayland clipboard proxy retains only a UTF-8 text payload. A file
selection that also advertises its URI as plain text would therefore be claimed
by Gamescope and republished without `text/uri-list`. For Gamescope destinations,
the bridge omits only that redundant text fallback while retaining the complete
file targets; ordinary text clipboard payloads are unchanged. It also publishes
the four-byte Windows `Preferred DropEffect` value for copy operations, allowing
Wine Explorer to accept the imported `CF_HDROP` file list.

Dolphin publishes its MIME data immediately, but KWin deliberately exposes a
native Wayland selection to XWayland only while an X11/XWayland window is
active. This focus gate prevents background X clients from snooping the
clipboard. When Gamescope takes focus away from Nested Desktop, the bridge
briefly releases the inner active window and reads the materialized selection
through Klipper. This is a bounded, transition-triggered operation rather than
continuous polling. Klipper's `clipboardHistoryUpdated` signal remains the
normal fast path for text and local file URIs: a sleeping D-Bus listener wakes
the worker's existing `select()` loop through a pipe only on updates. The X11
path remains the compatibility fallback and carries images, custom targets,
and systems without Klipper; equivalent late X11 updates are deduplicated.

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
