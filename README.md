# 4deus Mod

`4deus Mod` is a modular Decky Loader plugin for Steam Deck fixes and
customizations.

## Keyboard module

- Keeps the Steam keyboard above application windows when opened with a
  controller shortcut.
- Optionally keeps the keyboard open after pressing Enter.
- Adds a controller-friendly system-key layer with Ctrl, Fn, Esc, Delete, and
  F1-F12.
- Sends system keys through a dedicated Linux `uinput` keyboard so they reach
  the focused application.
- Supports holding the Steam items key to switch the system layer on or off.
- Shows letters from a second enabled Steam keyboard layout on each key.
- Supports automatic secondary-layout selection and a manually preferred
  layout.
- Reads layouts directly from Steam, so labels follow the layouts configured
  in Steam settings.
- Localizes plugin settings for every language currently supported by Steam.

Secondary labels are visual only. Steam remains responsible for the active
layout and text input.

## Interface

The Quick Access panel provides one activation row per mod. Detailed options
open in a native full-screen Decky settings route, keeping the panel compact as
new modules are added.

## Development

```bash
corepack enable pnpm
pnpm install
pnpm check
pnpm build
```

## License

MIT
