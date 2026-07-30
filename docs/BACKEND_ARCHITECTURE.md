# Backend architecture

Decky loads `main.py`, which intentionally contains no application logic. It
only exposes the `Plugin` class from `fourdeus_backend.plugin`.

## Plugin boundary

`fourdeus_backend.plugin` owns process lifecycle and system-key orchestration.
Decky RPC methods are grouped by feature under
`fourdeus_backend/endpoints/`:

- `developer.py` — developer mode and diagnostics;
- `controller.py` — controller recovery operations;
- `nested_desktop.py` — Nested Desktop and RustDesk settings;
- `system_tools.py` — App Bridge, MangoHud, and SteamOS tools.

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

## Nested Desktop

The executable `nested_desktop_mouse.py` remains the stable worker path used by
the supervisor. Its implementation lives in
`fourdeus_backend/nested_desktop/`:

- `discovery.py` finds sessions and input devices;
- `rustdesk.py` handles RustDesk protocols and translation;
- `bindings.py` parses Steam Deck reports and applies bindings;
- `x11.py`, `cursor.py`, and `eis.py` wrap their respective native APIs;
- `runtime_*.py` separate lifecycle, focus transitions, remote input, and HID
  ingestion;
- `supervisor.py` owns the worker subprocess and restart policy.

The top-level compatibility facades preserve existing imports for tests,
installed wrappers, and external tooling.
