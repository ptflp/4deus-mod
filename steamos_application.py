import os
from pathlib import Path
import shlex
from typing import Any

from steam_artwork import STEAM_ID64_BASE, SteamArtworkInstaller

STEAMOS_APP_NAME = "Steam Os"
STEAMOS_APP_ALIASES = (
    STEAMOS_APP_NAME,
    "Steam OS",
    "SteamOS",
    "Nested Desktop",
)
DEFAULT_NESTED_DESKTOP = Path("/usr/bin/steamos-nested-desktop")
DEFAULT_ASSET_DIRECTORY = Path(
    "/usr/share/applications/steam/steamos-nested-desktop"
)
DEFAULT_ARTWORK_DIRECTORY = (
    Path(__file__).resolve().parent / "assets/system-tools/steamos"
)


class SteamOsApplicationManager:
    def __init__(
        self,
        home: Path,
        nested_desktop: Path = DEFAULT_NESTED_DESKTOP,
        asset_directory: Path = DEFAULT_ASSET_DIRECTORY,
        artwork_directory: Path = DEFAULT_ARTWORK_DIRECTORY,
    ):
        self.home = Path(home)
        self.nested_desktop = Path(nested_desktop)
        self.asset_directory = Path(asset_directory)
        self.artwork_directory = Path(artwork_directory)
        self.wrapper_path = self.home / ".local/bin/4deus-steamos-desktop"
        self.artwork_installer = SteamArtworkInstaller(self.home)

    def status(self) -> dict[str, Any]:
        wrapper_installed = self.wrapper_path.is_file()
        return {
            "available": self.nested_desktop.is_file(),
            "current": wrapper_installed and self._wrapper_is_current(),
            "icon": str(self._asset("icon.png") or ""),
            "wrapperInstalled": wrapper_installed,
            "wrapperPath": str(self.wrapper_path),
        }

    def prepare(self) -> dict[str, Any]:
        if not self.nested_desktop.is_file():
            raise FileNotFoundError("SteamOS Nested Desktop is not available")

        self._write_wrapper()

        return {
            **self.status(),
            "aliases": list(STEAMOS_APP_ALIASES),
            "launchOptions": "",
            "launcherPath": str(self.wrapper_path),
            "name": STEAMOS_APP_NAME,
            "startDirectory": str(self.wrapper_path.parent),
        }

    def refresh_installed_wrapper(self) -> bool:
        if not self.wrapper_path.is_file():
            return False
        try:
            current = self.wrapper_path.read_text(encoding="utf-8")
        except OSError:
            return False
        if current == self._wrapper_contents():
            return False
        if (
            "KWIN_FORCE_SW_CURSOR=1" not in current
            or str(self.nested_desktop) not in current
        ):
            return False
        self._write_wrapper()
        return True

    def _write_wrapper(self):
        self.wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.wrapper_path.with_suffix(".tmp")
        temporary.write_text(self._wrapper_contents(), encoding="utf-8")
        temporary.chmod(0o755)
        os.replace(temporary, self.wrapper_path)

    def install_artwork(self, app_id: int) -> dict[str, Any]:
        sources = {
            slot: self.artwork_directory / f"{slot}.png"
            for slot in ("capsule", "grid", "hero", "logo")
        }
        missing = [
            path.name for path in sources.values() if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "SteamOS artwork is incomplete: "
                + ", ".join(sorted(missing))
            )
        return self.artwork_installer.install(
            app_id,
            sources,
            overwrite=True,
        )

    def _wrapper_contents(self) -> str:
        launcher = shlex.quote(str(self.nested_desktop))
        return (
            "#!/bin/sh\n"
            "\n"
            "unset LC_ALL\n"
            "export LANG=en_US.utf8\n"
            "export LC_CTYPE=en_US.utf8\n"
            "export GTK_IM_MODULE=ibus\n"
            "export QT_IM_MODULE=ibus\n"
            "export XMODIFIERS=@im=ibus\n"
            "\n"
            f'exec {launcher} "$@"\n'
        )

    def _wrapper_is_current(self) -> bool:
        try:
            return (
                self.wrapper_path.read_text(encoding="utf-8")
                == self._wrapper_contents()
                and bool(self.wrapper_path.stat().st_mode & 0o111)
            )
        except OSError:
            return False

    def _asset(self, name: str) -> Path | None:
        path = self.asset_directory / name
        return path if path.is_file() else None
