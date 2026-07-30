import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


SERVICE_NAME = "rustdesk.service"
DROPIN_NAME = "50-4deus-pointer-fix.conf"
MANAGED_MARKER = "# Managed by 4deus Mod: RustDesk pointer relay"


class RustDeskPointerFixManager:
    def __init__(
        self,
        home,
        plugin_root,
        *,
        systemctl_path="/usr/bin/systemctl",
        system_unit_directory="/etc/systemd/system",
        state_directory="/var/lib/4deus-mod",
        proc_root="/proc",
    ):
        self.home = Path(home)
        self.plugin_root = Path(plugin_root)
        self.systemctl_path = Path(systemctl_path)
        self.system_unit_directory = Path(system_unit_directory)
        self.state_directory = Path(state_directory)
        self.proc_root = Path(proc_root)
        self.source_library = (
            self.plugin_root / "bin/rustdesk-uinput-pointer-sync.so"
        )
        self.library = (
            self.state_directory / "rustdesk-uinput-pointer-sync.so"
        )
        self.dropin_directory = (
            self.system_unit_directory / f"{SERVICE_NAME}.d"
        )
        self.dropin = self.dropin_directory / DROPIN_NAME
        self.application_directory = (
            self.home / "Applications/RustDesk/usr/share/rustdesk"
        )
        self.executable = self.application_directory / "rustdesk"
        self.compatibility_libraries = (
            self.application_directory / "compat-libs"
        )

    def status(self):
        source_available = self._source_is_usable()
        installed = (
            self.library.is_file()
            and self._dropin_is_managed(self.dropin)
        )
        current = (
            installed
            and source_available
            and self._same_contents(self.source_library, self.library)
            and self._dropin_matches_expected_content()
        )
        service_state = self._service_state()
        return {
            "available": (
                os.geteuid() == 0
                and source_available
                and self.executable.is_file()
                and self.systemctl_path.is_file()
            ),
            "current": current,
            "installed": installed,
            "libraryPath": str(self.library),
            "runtimeLoaded": self._service_library_loaded(),
            "serviceState": service_state,
        }

    def install(self, *, restart=False):
        self._require_root()
        if not self._source_is_usable():
            raise RuntimeError(
                "The packaged RustDesk pointer fix is unavailable"
            )
        if not self.executable.is_file():
            raise RuntimeError("RustDesk installation was not found")

        previous_state = self._service_state()
        library_changed = self._copy_library()
        dropin_changed = self._write_dropin()
        if dropin_changed or self._daemon_reload_needed():
            self._systemctl("daemon-reload")

        loaded_library = self._service_loaded_library()
        runtime_loaded = loaded_library is not None
        updated_loaded_library = (
            library_changed and loaded_library == "installed"
        )
        if restart and previous_state in {
            "active",
            "activating",
            "reloading",
        } and (updated_loaded_library or not runtime_loaded):
            self._systemctl("restart", SERVICE_NAME)
        elif restart and previous_state == "failed":
            self._systemctl("reset-failed", SERVICE_NAME)
            self._systemctl("restart", SERVICE_NAME)

        return self.status()

    def remove(self):
        self._require_root()
        previous_state = self._service_state()
        removed = False
        if self._dropin_is_managed(self.dropin):
            self.dropin.unlink()
            removed = True

        if removed:
            self._systemctl("daemon-reload")
            if previous_state in {
                "active",
                "activating",
                "reloading",
            }:
                self._systemctl("restart", SERVICE_NAME)

        if self.library.is_file() and not self._dropin_references_library():
            self.library.unlink()
        self._remove_empty_directory(self.dropin_directory)
        self._remove_empty_directory(self.state_directory)
        return self.status()

    def _require_root(self):
        if os.geteuid() != 0:
            raise PermissionError(
                "The RustDesk pointer fix requires Decky root access"
            )

    def _copy_library(self):
        if self._same_contents(self.source_library, self.library):
            return False
        self.state_directory.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.state_directory,
            prefix=f".{self.library.name}.",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as destination:
                with self.source_library.open("rb") as source:
                    shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
            temporary.chmod(0o644)
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
        executable = self._systemd_quote(str(self.executable))
        working_directory = self._systemd_path(
            str(self.application_directory)
        )
        library = self._systemd_environment_value(
            "LD_PRELOAD",
            str(self.library),
        )
        compatibility_libraries = self._systemd_environment_value(
            "LD_LIBRARY_PATH",
            str(self.compatibility_libraries),
        )
        return (
            f"{MANAGED_MARKER}\n"
            "[Service]\n"
            "ExecStart=\n"
            f"ExecStart={executable} --service\n"
            f"WorkingDirectory={working_directory}\n"
            f"Environment={library}\n"
            f"Environment={compatibility_libraries}\n"
            'Environment="DISPLAY=:0"\n'
            'Environment="XDG_SESSION_TYPE=x11"\n'
            'Environment="XDG_CURRENT_DESKTOP=gamescope"\n'
            'Environment="XDG_SESSION_DESKTOP=gamescope"\n'
        )

    @staticmethod
    def _systemd_quote(value):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("%", "%%")
        )
        return f'"{escaped}"'

    @staticmethod
    def _systemd_path(value):
        if (
            not value.startswith("/")
            or any(character.isspace() for character in value)
        ):
            raise ValueError("RustDesk path is not safe for a systemd unit")
        return value.replace("%", "%%")

    @classmethod
    def _systemd_environment_value(cls, name, value):
        return cls._systemd_quote(f"{name}={value}")

    def _dropin_matches_expected_content(self):
        try:
            return (
                self.dropin.is_file()
                and self.dropin.read_text(encoding="utf-8")
                == self._dropin_content()
            )
        except OSError:
            return False

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

    def _dropin_references_library(self):
        if not self.dropin_directory.is_dir():
            return False
        for candidate in self.dropin_directory.glob("*.conf"):
            try:
                if str(self.library) in candidate.read_text(
                    encoding="utf-8"
                ):
                    return True
            except OSError:
                continue
        return False

    def _service_library_loaded(self):
        return self._service_loaded_library() is not None

    def _service_loaded_library(self):
        process_id = self._service_main_pid()
        if process_id <= 0:
            return None
        try:
            mappings = (
                self.proc_root / str(process_id) / "maps"
            ).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if str(self.source_library) in mappings:
            return "source"
        if str(self.library) in mappings:
            return "installed"
        return None

    def _service_main_pid(self):
        try:
            result = self._systemctl(
                "show",
                SERVICE_NAME,
                "--property=MainPID",
                "--value",
                check=False,
            )
            return int(result.stdout.strip() or "0")
        except (OSError, ValueError):
            return 0

    def _service_state(self):
        try:
            result = self._systemctl(
                "is-active",
                SERVICE_NAME,
                check=False,
            )
        except OSError:
            return "unknown"
        return result.stdout.strip() or "unknown"

    def _daemon_reload_needed(self):
        try:
            result = self._systemctl(
                "show",
                SERVICE_NAME,
                "--property=NeedDaemonReload",
                "--value",
                check=False,
            )
        except OSError:
            return False
        return result.stdout.strip() == "yes"

    def _systemctl(self, *arguments, check=True):
        environment = os.environ.copy()
        original_library_path = environment.pop(
            "LD_LIBRARY_PATH_ORIG",
            None,
        )
        if original_library_path:
            environment["LD_LIBRARY_PATH"] = original_library_path
        else:
            environment.pop("LD_LIBRARY_PATH", None)
        environment.pop("LD_PRELOAD", None)
        environment.pop("LD_AUDIT", None)
        result = subprocess.run(
            [str(self.systemctl_path), *arguments],
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

    @staticmethod
    def _same_contents(first, second):
        if not first.is_file() or not second.is_file():
            return False
        try:
            if first.stat().st_size != second.stat().st_size:
                return False
            return (
                RustDeskPointerFixManager._digest(first)
                == RustDeskPointerFixManager._digest(second)
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
