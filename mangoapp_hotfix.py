import hashlib
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile


SERVICE_NAME = "gamescope-mangoapp.service"
DROPIN_NAME = "50-4deus-mangoapp-fd-guard.conf"
LEGACY_DROPIN_NAME = "override.conf"
MANAGED_MARKER = "# Managed by 4deus Mod: MangoHud process FD guard"


class MangoHudFixManager:
    def __init__(
        self,
        home,
        plugin_root,
        *,
        mangoapp_path="/usr/bin/mangoapp",
        systemctl_path="/usr/bin/systemctl",
    ):
        self.home = Path(home)
        self.plugin_root = Path(plugin_root)
        self.mangoapp_path = Path(mangoapp_path)
        self.systemctl_path = Path(systemctl_path)
        self.source_library = (
            self.plugin_root / "bin/mangoapp-fdinfo-guard.so"
        )
        self.library = (
            self.home
            / ".local/lib/4deus-mod/mangoapp-fdinfo-guard.so"
        )
        self.dropin_directory = (
            self.home
            / ".config/systemd/user"
            / f"{SERVICE_NAME}.d"
        )
        self.dropin = self.dropin_directory / DROPIN_NAME
        self.legacy_dropin = (
            self.dropin_directory / LEGACY_DROPIN_NAME
        )
        self.user_id = self.home.stat().st_uid

    def status(self):
        preferred_installed = self._dropin_is_managed(self.dropin)
        preferred_current = self._dropin_matches_expected_content()
        legacy_installed = self._legacy_dropin_matches()
        library_installed = self.library.is_file()
        source_available = self._source_is_usable()
        current = (
            preferred_current
            and source_available
            and self._same_contents(self.source_library, self.library)
        )
        return {
            "available": (
                source_available
                and self.mangoapp_path.is_file()
                and self.systemctl_path.is_file()
            ),
            "current": current,
            "installed": (
                library_installed
                and (preferred_installed or legacy_installed)
            ),
            "libraryPath": str(self.library),
            "serviceState": self._service_state(),
        }

    def install(self):
        if not self._source_is_usable():
            raise RuntimeError("The packaged MangoHud fix is unavailable")
        if not self.mangoapp_path.is_file():
            raise RuntimeError("MangoApp is not installed on this system")

        previous_state = self._service_state()
        binary_changed = self._copy_library()
        dropin_changed = self._write_dropin()
        legacy_removed = self._remove_matching_legacy_dropin()

        if binary_changed or dropin_changed or legacy_removed:
            self._systemctl("daemon-reload")
            self._restart_after_change(previous_state)

        return self.status()

    def remove(self):
        previous_state = self._service_state()
        removed = False

        if self._dropin_is_managed(self.dropin):
            self.dropin.unlink()
            removed = True
        if self._remove_matching_legacy_dropin():
            removed = True

        if removed:
            self._systemctl("daemon-reload")
            if previous_state in {"active", "activating", "reloading"}:
                self._systemctl("restart", SERVICE_NAME)

        if (
            self.library.is_file()
            and not self._remaining_dropin_references_library()
        ):
            self.library.unlink()
        self._remove_empty_directory(self.library.parent)
        self._remove_empty_directory(self.dropin_directory)

        return self.status()

    def _copy_library(self):
        if self._same_contents(self.source_library, self.library):
            return False

        self.library.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.library.parent,
            prefix=f".{self.library.name}.",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as destination:
                with self.source_library.open("rb") as source:
                    shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
            temporary.chmod(0o755)
            os.replace(temporary, self.library)
        finally:
            if temporary.exists():
                temporary.unlink()
        return True

    def _write_dropin(self):
        content = self._dropin_content()
        if self.dropin.is_file():
            try:
                if self.dropin.read_text(encoding="utf-8") == content:
                    return False
            except OSError:
                pass

        self.dropin_directory.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.dropin_directory,
            prefix=f".{self.dropin.name}.",
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
            ) as destination:
                destination.write(content)
                destination.flush()
                os.fsync(destination.fileno())
            temporary.chmod(0o644)
            os.replace(temporary, self.dropin)
        finally:
            if temporary.exists():
                temporary.unlink()
        return True

    def _dropin_content(self):
        library = (
            str(self.library)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("%", "%%")
        )
        return (
            f"{MANAGED_MARKER}\n"
            "[Service]\n"
            f'Environment="LD_PRELOAD={library}"\n'
        )

    def _legacy_dropin_content(self):
        return (
            "[Service]\n"
            f"Environment=LD_PRELOAD={self.library}\n"
            "ExecStart=\n"
            "ExecStart=/usr/bin/mangoapp\n"
        )

    def _legacy_dropin_matches(self):
        try:
            return (
                self.legacy_dropin.is_file()
                and self.legacy_dropin.read_text(encoding="utf-8")
                == self._legacy_dropin_content()
            )
        except OSError:
            return False

    def _dropin_matches_expected_content(self):
        try:
            return (
                self.dropin.is_file()
                and self.dropin.read_text(encoding="utf-8")
                == self._dropin_content()
            )
        except OSError:
            return False

    def _remove_matching_legacy_dropin(self):
        if not self._legacy_dropin_matches():
            return False
        self.legacy_dropin.unlink()
        return True

    @staticmethod
    def _dropin_is_managed(path):
        try:
            return (
                path.is_file()
                and path.read_text(encoding="utf-8").startswith(
                    f"{MANAGED_MARKER}\n"
                )
            )
        except OSError:
            return False

    def _source_is_usable(self):
        try:
            with self.source_library.open("rb") as source:
                header = source.read(20)
        except OSError:
            return False
        return (
            len(header) >= 20
            and header[:4] == b"\x7fELF"
            and header[4] == 2
            and int.from_bytes(header[18:20], "little") == 62
        )

    def _remaining_dropin_references_library(self):
        if not self.dropin_directory.is_dir():
            return False
        for candidate in self.dropin_directory.glob("*.conf"):
            try:
                if str(self.library) in candidate.read_text(encoding="utf-8"):
                    return True
            except OSError:
                continue
        return False

    def _service_state(self):
        try:
            result = self._systemctl(
                "is-active",
                SERVICE_NAME,
                check=False,
            )
        except OSError:
            return "unknown"
        state = result.stdout.strip()
        return state or "unknown"

    def _restart_after_change(self, previous_state):
        if previous_state == "failed":
            self._systemctl("reset-failed", SERVICE_NAME)
            self._systemctl("restart", SERVICE_NAME)
        elif previous_state in {"active", "activating", "reloading"}:
            self._systemctl("restart", SERVICE_NAME)

    def _systemctl(self, *arguments, check=True):
        environment = os.environ.copy()
        runtime_directory = f"/run/user/{self.user_id}"
        environment["XDG_RUNTIME_DIR"] = runtime_directory
        environment["DBUS_SESSION_BUS_ADDRESS"] = (
            f"unix:path={runtime_directory}/bus"
        )

        command = [str(self.systemctl_path), "--user", *arguments]
        if os.geteuid() == 0 and self.user_id != 0:
            username = pwd.getpwuid(self.user_id).pw_name
            command = [
                "/usr/bin/runuser",
                "-u",
                username,
                "--",
                *command,
            ]

        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=environment,
            text=True,
            timeout=15,
        )
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"systemctl {' '.join(arguments)} failed: {detail}"
            )
        return result

    @staticmethod
    def _same_contents(first, second):
        if not first.is_file() or not second.is_file():
            return False
        try:
            if first.stat().st_size != second.stat().st_size:
                return False
            return (
                MangoHudFixManager._digest(first)
                == MangoHudFixManager._digest(second)
            )
        except OSError:
            return False

    @staticmethod
    def _digest(path):
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.digest()

    @staticmethod
    def _remove_empty_directory(path):
        try:
            path.rmdir()
        except OSError:
            pass
