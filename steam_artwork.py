import os
from pathlib import Path
import re
import shutil
from typing import Any, Mapping


STEAM_ID64_BASE = 76561197960265728
LOGIN_USER_PATTERN = re.compile(
    r'"(?P<steam_id>\d{17})"\s*\{(?P<body>[^{}]*)\}',
    re.DOTALL,
)
ARTWORK_DESTINATIONS = {
    "capsule": "{app_id}p.png",
    "grid": "{app_id}.png",
    "hero": "{app_id}_hero.png",
    "logo": "{app_id}_logo.png",
}


class SteamArtworkInstaller:
    def __init__(self, home: Path):
        self.home = Path(home)

    def install(
        self,
        app_id: int,
        sources: Mapping[str, Path | None],
        overwrite: bool = False,
    ) -> dict[str, Any]:
        self._validate_app_id(app_id)
        unknown_slots = set(sources) - set(ARTWORK_DESTINATIONS)
        if unknown_slots:
            raise ValueError(
                f"Unknown Steam artwork slots: {', '.join(sorted(unknown_slots))}"
            )

        config_directory = self._current_steam_config_directory()
        if config_directory is None:
            raise FileNotFoundError("The active Steam user was not found")

        grid_directory = config_directory / "grid"
        grid_directory.mkdir(parents=True, exist_ok=True)
        installed = 0
        preserved = 0
        replaced = 0
        for slot, destination_template in ARTWORK_DESTINATIONS.items():
            source = sources.get(slot)
            if source is None or not source.is_file():
                continue
            destination = grid_directory / destination_template.format(
                app_id=app_id
            )
            if destination.exists():
                if not overwrite:
                    preserved += 1
                    continue
                replaced += 1
            temporary = destination.with_name(
                f".{destination.name}.4deus-mod.tmp"
            )
            shutil.copyfile(source, temporary)
            temporary.chmod(0o644)
            os.replace(temporary, destination)
            installed += 1

        return {
            "gridDirectory": str(grid_directory),
            "installed": installed,
            "preserved": preserved,
            "replaced": replaced,
        }

    @staticmethod
    def _validate_app_id(app_id: int) -> None:
        if isinstance(app_id, bool) or not isinstance(app_id, int):
            raise ValueError("Steam shortcut AppID must be an integer")
        if app_id < 1 or app_id > 0xFFFFFFFF:
            raise ValueError("Steam shortcut AppID is out of range")

    def _current_steam_config_directory(self) -> Path | None:
        user_data_directories = self._steam_userdata_directories()
        for account_id in self._login_account_ids():
            for user_data in user_data_directories:
                config = user_data / str(account_id) / "config"
                if config.is_dir():
                    return config

        candidates = [
            account / "config"
            for user_data in user_data_directories
            if user_data.is_dir()
            for account in user_data.iterdir()
            if account.name.isdigit() and (account / "config").is_dir()
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda path: self._modification_time(
                path / "localconfig.vdf"
            ),
        )

    def _login_account_ids(self) -> list[int]:
        users: list[tuple[int, int, int]] = []
        seen: set[int] = set()
        for steam_root in self._steam_roots():
            login_users = steam_root / "config/loginusers.vdf"
            try:
                contents = login_users.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            for match in LOGIN_USER_PATTERN.finditer(contents):
                steam_id = int(match.group("steam_id"))
                account_id = steam_id - STEAM_ID64_BASE
                if account_id < 1 or account_id > 0xFFFFFFFF:
                    continue
                body = match.group("body")
                automatic = int(
                    bool(re.search(r'"AutoLogin"\s*"1"', body))
                )
                timestamp_match = re.search(
                    r'"Timestamp"\s*"(?P<timestamp>\d+)"',
                    body,
                )
                timestamp = (
                    int(timestamp_match.group("timestamp"))
                    if timestamp_match
                    else 0
                )
                if account_id not in seen:
                    users.append((automatic, timestamp, account_id))
                    seen.add(account_id)
        users.sort(reverse=True)
        return [account_id for _, _, account_id in users]

    def _steam_roots(self) -> list[Path]:
        return self._unique_paths(
            [
                self.home / ".local/share/Steam",
                self.home / ".steam/steam",
            ]
        )

    def _steam_userdata_directories(self) -> list[Path]:
        return self._unique_paths(
            [root / "userdata" for root in self._steam_roots()]
        )

    @staticmethod
    def _unique_paths(paths: list[Path]) -> list[Path]:
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path.resolve(strict=False))
            if key not in seen:
                unique.append(path)
                seen.add(key)
        return unique

    @staticmethod
    def _modification_time(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0
