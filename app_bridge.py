import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any

from steam_artwork import SteamArtworkInstaller


PROFILE_VERSION = 1
CHROME_APP_ID = "com.google.Chrome"
CHROME_PROFILE_ID = "chrome"
PARSEC_APP_ID = "com.parsecgaming.parsec"
PARSEC_PROFILE_ID = "parsec"
RUSTDESK_FLATPAK_APP_ID = "com.rustdesk.RustDesk"
RUSTDESK_PROFILE_ID = "rustdesk"
TERMINAL_EXECUTABLE = Path("/usr/bin/konsole")
TERMINAL_PROFILE_ID = "terminal"
TERMINAL_SYSTEM_ICON_PATHS = (
    Path("/usr/share/icons/breeze/apps/64/utilities-terminal.svg"),
    Path(
        "/usr/share/icons/AdwaitaLegacy/48x48/legacy/"
        "utilities-terminal.png"
    ),
)
PROFILE_ID_PATTERN = re.compile(r"[^a-z0-9-]+")
DESKTOP_FIELD_CODE_PATTERN = re.compile(r"^%[fFuUdDnNickvm]$")


def normalize_profile_id(value: str) -> str:
    normalized = PROFILE_ID_PATTERN.sub("-", value.strip().lower()).strip("-")
    return normalized[:64]


def _clean_text(value: Any, maximum: int = 4096) -> str:
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _desktop_command(raw: str) -> tuple[str, str] | None:
    try:
        parts = [
            part
            for part in shlex.split(raw)
            if not DESKTOP_FIELD_CODE_PATTERN.match(part)
        ]
    except ValueError:
        return None
    if not parts:
        return None
    return parts[0], shlex.join(parts[1:])


class AppBridgeManager:
    def __init__(
        self,
        home: Path,
        plugin_root: Path,
        *,
        terminal_executable: Path = TERMINAL_EXECUTABLE,
    ):
        self.home = Path(home)
        self.plugin_root = Path(plugin_root)
        self.data_dir = self.home / ".local/share/4deus-mod/app-bridge"
        self.profile_dir = self.data_dir / "profiles"
        self.runner_source = self.plugin_root / "bin/4deus-app-bridge"
        self.runner_path = self.home / ".local/bin/4deus-app-bridge"
        self.artwork_root = self.plugin_root / "assets/app-bridge"
        self.artwork_installer = SteamArtworkInstaller(self.home)
        self.terminal_executable = Path(terminal_executable)

    def status(self) -> dict[str, Any]:
        return {
            "launcherInstalled": self._runner_is_current(),
            "launcherPath": str(self.runner_path),
            "chromeInstalled": self._flatpak_installed(CHROME_APP_ID),
            "chromeProfileInstalled": (
                self.profile_dir / f"{CHROME_PROFILE_ID}.json"
            ).is_file(),
            "parsecInstalled": self._flatpak_installed(PARSEC_APP_ID),
            "parsecProfileInstalled": (
                self.profile_dir / f"{PARSEC_PROFILE_ID}.json"
            ).is_file(),
            "rustdeskFlatpakInstalled": (
                self.rustdesk_flatpak_installed()
            ),
            "rustdeskInstalled": self.rustdesk_unpacked_installed(),
            "rustdeskProfileInstalled": (
                self.profile_dir / f"{RUSTDESK_PROFILE_ID}.json"
            ).is_file(),
            "terminalInstalled": self.terminal_executable.is_file(),
            "terminalProfileInstalled": (
                self.profile_dir / f"{TERMINAL_PROFILE_ID}.json"
            ).is_file(),
        }

    def list_applications(self) -> list[dict[str, str]]:
        applications: dict[str, dict[str, str]] = {}
        self._collect_flatpaks(applications)
        self._collect_desktop_files(applications)
        return sorted(
            applications.values(),
            key=lambda application: application["name"].casefold(),
        )

    def prepare_parsec(self) -> dict[str, Any]:
        working_directory = (
            self.home
            / ".local/share/flatpak/app/com.parsecgaming.parsec/current/"
            "active/files/bin"
        )
        icon = self._first_existing(
            [
                Path(
                    "/var/lib/flatpak/exports/share/icons/hicolor/512x512/"
                    "apps/com.parsecgaming.parsec.png"
                ),
                self.home
                / ".local/share/flatpak/exports/share/icons/hicolor/512x512/"
                "apps/com.parsecgaming.parsec.png",
            ]
        )
        prepared = self.save_profile(
            {
                "id": PARSEC_PROFILE_ID,
                "name": "Parsec",
                "executable": "/usr/bin/flatpak",
                "arguments": (
                    "run --branch=stable --arch=x86_64 "
                    "--command=/app/bin/parsec com.parsecgaming.parsec"
                ),
                "workingDirectory": str(working_directory),
                "icon": str(icon) if icon else "",
                "waitForProcess": "/app/extra/bin/parsecd",
                "clearSteamPreload": False,
                "sanitizeSteamOverlay": True,
                "forceX11": False,
                "libraryPath": "",
            }
        )
        return {**prepared, "artworkId": PARSEC_PROFILE_ID}

    def prepare_chrome(self) -> dict[str, Any]:
        if not self._flatpak_installed(CHROME_APP_ID):
            raise FileNotFoundError("Google Chrome installation was not found")
        bundled_icon = self.artwork_root / CHROME_PROFILE_ID / "icon.png"
        prepared = self.save_profile(
            {
                "id": CHROME_PROFILE_ID,
                "name": "Google Chrome",
                "executable": "/usr/bin/flatpak",
                "arguments": (
                    "run --branch=stable --arch=x86_64 --command=chrome "
                    f"{CHROME_APP_ID} --window-position=0,0 "
                    "--window-size=1280,800 --start-maximized"
                ),
                "workingDirectory": str(self.home),
                "icon": (
                    str(bundled_icon)
                    if bundled_icon.is_file()
                    else self._resolve_icon(CHROME_APP_ID)
                ),
                "waitForProcess": "",
                "clearSteamPreload": True,
                "sanitizeSteamOverlay": False,
                "forceX11": False,
                "libraryPath": "",
            }
        )
        return {
            **prepared,
            "aliases": ["Chrome"],
            "artworkId": CHROME_PROFILE_ID,
        }

    def prepare_rustdesk(self) -> dict[str, Any]:
        if self.rustdesk_flatpak_installed():
            raise RuntimeError(
                "RustDesk Flatpak is unsupported; remove it and install "
                "the unpacked Arch Linux package"
            )
        application_directory = self._rustdesk_directory()
        executable = application_directory / "rustdesk"
        if not executable.is_file():
            raise FileNotFoundError("RustDesk installation was not found")
        icon = (
            self.home
            / "Applications/RustDesk/usr/share/icons/hicolor/256x256/"
            "apps/rustdesk.png"
        )
        prepared = self.save_profile(
            {
                "id": RUSTDESK_PROFILE_ID,
                "name": "RustDesk",
                "executable": str(executable),
                "arguments": "",
                "workingDirectory": str(application_directory),
                "icon": str(icon) if icon.is_file() else "",
                "waitForProcess": str(executable),
                "clearSteamPreload": True,
                "forceX11": True,
                "useNestedDesktopRuntime": True,
                "libraryPath": str(application_directory / "compat-libs"),
            }
        )
        return {**prepared, "artworkId": RUSTDESK_PROFILE_ID}

    def prepare_terminal(self) -> dict[str, Any]:
        if not self.terminal_executable.is_file():
            raise FileNotFoundError("Konsole installation was not found")
        bundled_icon = (
            self.artwork_root / TERMINAL_PROFILE_ID / "icon.png"
        )
        icon = self._first_existing(
            [bundled_icon, *TERMINAL_SYSTEM_ICON_PATHS]
        )
        prepared = self.save_profile(
            {
                "id": TERMINAL_PROFILE_ID,
                "name": "Terminal",
                "executable": str(self.terminal_executable),
                "arguments": "",
                "workingDirectory": str(self.home),
                "icon": str(icon) if icon else "",
                "waitForProcess": str(self.terminal_executable),
                "clearSteamPreload": True,
                "forceX11": False,
                "libraryPath": "",
            }
        )
        return {**prepared, "artworkId": TERMINAL_PROFILE_ID}

    def install_artwork(
        self,
        artwork_id: str,
        app_id: int,
    ) -> dict[str, Any]:
        if artwork_id not in (
            CHROME_PROFILE_ID,
            PARSEC_PROFILE_ID,
            RUSTDESK_PROFILE_ID,
            TERMINAL_PROFILE_ID,
        ):
            raise ValueError("Artwork is not available for this profile")
        asset_directory = self.artwork_root / artwork_id
        sources = {
            slot: asset_directory / f"{slot}.png"
            for slot in ("capsule", "grid", "hero", "logo")
        }
        missing = [
            path.name for path in sources.values() if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "App Bridge artwork is incomplete: "
                + ", ".join(sorted(missing))
            )
        return {
            **self.artwork_installer.install(
                app_id,
                sources,
                overwrite=True,
            ),
            "artworkId": artwork_id,
        }

    def save_profile(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Profile must be an object")
        name = _clean_text(raw.get("name"), 128)
        executable = _clean_text(raw.get("executable"))
        if not name or not executable:
            raise ValueError("Profile name and executable are required")
        if not Path(executable).is_absolute():
            raise ValueError("Executable path must be absolute")

        profile_id = normalize_profile_id(_clean_text(raw.get("id"), 128) or name)
        if not profile_id:
            raise ValueError("Profile ID is invalid")
        arguments = _clean_text(raw.get("arguments"))
        try:
            command = [executable, *shlex.split(arguments)]
        except ValueError as error:
            raise ValueError(f"Invalid arguments: {error}") from error

        working_directory = _clean_text(raw.get("workingDirectory"))
        icon = _clean_text(raw.get("icon"))
        clear_steam_preload = bool(raw.get("clearSteamPreload"))
        profile = {
            "version": PROFILE_VERSION,
            "id": profile_id,
            "name": name,
            "command": command,
            "workingDirectory": working_directory,
            "icon": icon,
            "waitForProcess": _clean_text(raw.get("waitForProcess"), 512),
            "clearSteamPreload": clear_steam_preload,
            "sanitizeSteamOverlay": (
                bool(raw.get("sanitizeSteamOverlay"))
                and not clear_steam_preload
            ),
            "forceX11": bool(raw.get("forceX11")),
            "useNestedDesktopRuntime": bool(
                raw.get("useNestedDesktopRuntime")
            ),
            "libraryPath": _clean_text(raw.get("libraryPath")),
        }

        self._install_runner()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        destination = self.profile_dir / f"{profile_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
        return {
            "icon": icon,
            "id": profile_id,
            "launcherPath": str(self.runner_path),
            "name": name,
            "startDirectory": (
                working_directory
                if Path(working_directory).is_absolute()
                else str(self.runner_path.parent)
            ),
        }

    def _install_runner(self) -> None:
        if not self.runner_source.is_file():
            raise FileNotFoundError("App Bridge runner is missing from the plugin")
        self.runner_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.runner_path.with_suffix(".tmp")
        shutil.copyfile(self.runner_source, temporary)
        temporary.chmod(0o755)
        os.replace(temporary, self.runner_path)

    def refresh_installed_runner(self) -> bool:
        if not self.runner_path.is_file() or self._runner_is_current():
            return False
        self._install_runner()
        return True

    def _rustdesk_directory(self) -> Path:
        return self.home / "Applications/RustDesk/usr/share/rustdesk"

    def rustdesk_flatpak_installed(self) -> bool:
        return self._flatpak_files_installed(RUSTDESK_FLATPAK_APP_ID)

    def rustdesk_unpacked_installed(self) -> bool:
        return (self._rustdesk_directory() / "rustdesk").is_file()

    def _runner_is_current(self) -> bool:
        if not self.runner_source.is_file() or not self.runner_path.is_file():
            return False
        return self._file_digest(self.runner_source) == self._file_digest(
            self.runner_path
        )

    @staticmethod
    def _file_digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _first_existing(paths: list[Path]) -> Path | None:
        return next((path for path in paths if path.is_file()), None)

    def _flatpak_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.pop("LD_PRELOAD", None)
        environment.pop("LD_AUDIT", None)
        environment["HOME"] = str(self.home)
        environment["XDG_DATA_HOME"] = str(self.home / ".local/share")
        return environment

    def _flatpak_installed(self, application_id: str) -> bool:
        if self._flatpak_files_installed(application_id):
            return True
        try:
            result = subprocess.run(
                ["/usr/bin/flatpak", "info", application_id],
                check=False,
                capture_output=True,
                env=self._flatpak_environment(),
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def _flatpak_files_installed(self, application_id: str) -> bool:
        installation_paths = [
            self.home
            / ".local/share/flatpak/exports/share/applications"
            / f"{application_id}.desktop",
            Path("/var/lib/flatpak/exports/share/applications")
            / f"{application_id}.desktop",
            self.home / ".local/share/flatpak/app" / application_id,
            Path("/var/lib/flatpak/app") / application_id,
        ]
        return any(path.exists() for path in installation_paths)

    def _collect_flatpaks(
        self,
        applications: dict[str, dict[str, str]],
    ) -> None:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/flatpak",
                    "list",
                    "--app",
                    "--columns=application,name",
                ],
                check=False,
                capture_output=True,
                env=self._flatpak_environment(),
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            application_id, name = (part.strip() for part in parts)
            if not application_id or not name:
                continue
            applications[f"flatpak:{application_id}"] = {
                "arguments": f"run {shlex.quote(application_id)}",
                "executable": "/usr/bin/flatpak",
                "icon": self._resolve_icon(application_id),
                "id": f"flatpak:{application_id}",
                "kind": "flatpak",
                "name": name,
                "workingDirectory": str(self.home),
            }

    def _collect_desktop_files(
        self,
        applications: dict[str, dict[str, str]],
    ) -> None:
        directories = [
            self.home / ".local/share/applications",
            self.home / ".local/share/flatpak/exports/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path("/usr/share/applications"),
        ]
        for directory in directories:
            if not directory.is_dir():
                continue
            for desktop_file in directory.glob("*.desktop"):
                application = self._read_desktop_file(desktop_file)
                if application is None:
                    continue
                key = application["id"]
                existing = applications.get(key)
                if existing and existing["kind"] == "flatpak":
                    existing["icon"] = application["icon"]
                    continue
                applications.setdefault(key, application)

    def _read_desktop_file(self, path: Path) -> dict[str, str] | None:
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        try:
            parser.read(path, encoding="utf-8")
            entry = parser["Desktop Entry"]
        except (OSError, UnicodeError, KeyError, configparser.Error):
            return None
        if entry.get("Type", "Application") != "Application":
            return None
        if entry.get("NoDisplay", "false").lower() == "true":
            return None
        name = entry.get("Name", "").strip()
        command = _desktop_command(entry.get("Exec", ""))
        if not name or command is None:
            return None
        executable, arguments = command
        if not Path(executable).is_absolute():
            resolved_executable = shutil.which(executable)
            if not resolved_executable:
                return None
            executable = resolved_executable
        flatpak_id = entry.get("X-Flatpak", "").strip()
        application_id = (
            f"flatpak:{flatpak_id}"
            if flatpak_id
            else f"desktop:{path.stem}"
        )
        return {
            "arguments": arguments,
            "executable": executable,
            "icon": self._resolve_icon(entry.get("Icon", "").strip()),
            "id": application_id,
            "kind": "flatpak" if flatpak_id else "desktop",
            "name": name,
            "workingDirectory": entry.get("Path", "").strip() or str(self.home),
        }

    def _resolve_icon(self, value: str) -> str:
        if not value:
            return ""
        icon = Path(value)
        if icon.is_absolute():
            return str(icon) if icon.is_file() else ""
        basename = icon.name
        names = (
            [basename]
            if icon.suffix.lower() in {".png", ".svg", ".xpm"}
            else [f"{basename}.png", f"{basename}.svg"]
        )
        roots = [
            self.home / ".local/share/icons/hicolor",
            self.home / ".local/share/flatpak/exports/share/icons/hicolor",
            Path("/var/lib/flatpak/exports/share/icons/hicolor"),
            Path("/usr/share/icons/hicolor"),
        ]
        preferred_sizes = ["512x512", "256x256", "128x128", "scalable"]
        for root in roots:
            for size in preferred_sizes:
                for name in names:
                    candidate = root / size / "apps" / name
                    if candidate.is_file():
                        return str(candidate)
        for name in names:
            candidate = Path("/usr/share/pixmaps") / name
            if candidate.is_file():
                return str(candidate)
        return ""
