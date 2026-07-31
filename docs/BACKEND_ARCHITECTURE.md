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
- `x11.py`, `cursor.py`, and `eis.py` wrap their respective native APIs;
- `runtime_*.py` separate lifecycle, focus transitions, remote input, and HID
  ingestion;
- `supervisor.py` owns the worker subprocess and restart policy.

The Nested Desktop master switch is persisted separately from mouse, binding,
touchscreen, inertia, and RustDesk preferences. It stops the worker without
overwriting those child settings, then restores the same configuration when
re-enabled.

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
