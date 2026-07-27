# 4deus Mod

`4deus Mod` is a modular Decky Loader plugin for Steam Deck fixes and
customizations.

## Keyboard module

- Keeps the Steam keyboard above application windows when opened with a
  controller shortcut.
- Shows letters from a second enabled Steam keyboard layout on each key.
- Supports automatic secondary-layout selection and a manually preferred
  layout.
- Reads layouts directly from Steam, so labels follow the layouts configured
  in Steam settings.

Secondary labels are visual only. Steam remains responsible for the active
layout and text input.

## Development

```bash
corepack enable pnpm
pnpm install
pnpm check
pnpm build
```

## License

MIT
