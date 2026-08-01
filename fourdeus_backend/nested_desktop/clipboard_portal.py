"""Desktop portal sessions for sandbox-safe clipboard file transfers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import stat
from typing import Callable, Iterable
from urllib.parse import unquote, urlsplit


LOGGER = logging.getLogger("4deus-nested-mouse")
PORTAL_BUS_NAME = "org.freedesktop.portal.Documents"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/documents"
PORTAL_INTERFACE = "org.freedesktop.portal.FileTransfer"
PORTAL_FD_BATCH_SIZE = 12
DOCUMENTS_INTERFACE = "org.freedesktop.portal.Documents"
DOCUMENT_REUSE_EXISTING = 1
DOCUMENT_EXPORT_DIRECTORY = 8


def outer_session_bus_address(uid: int | None = None) -> str:
    """Return the canonical host user bus, outside nested sessions."""
    user_id = os.getuid() if uid is None else uid
    return f"unix:path=/run/user/{user_id}/bus"


def active_flatpak_app_ids(
    runtime_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return active Flatpak application IDs without spawning flatpak(1)."""
    runtime_root = runtime_dir or Path(f"/run/user/{os.getuid()}")
    instance_root = runtime_root / ".flatpak"
    app_ids = []
    try:
        info_files = instance_root.glob("*/info")
    except OSError:
        return ()
    for info_file in info_files:
        try:
            lines = info_file.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            continue
        section = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1]
                continue
            if section != "Application" or not stripped.startswith("name="):
                continue
            app_id = stripped.removeprefix("name=").strip()
            if app_id and "/" not in app_id and app_id not in app_ids:
                app_ids.append(app_id)
            break
    return tuple(app_ids)


class DocumentPortalExporter:
    """Expose host files at URIs readable by active Flatpak applications."""

    def __init__(
        self,
        bus_address: str | None = None,
        *,
        interface=None,
        fd_wrapper: Callable[[int], object] | None = None,
        opener: Callable[[Path], int] | None = None,
        app_ids_provider: Callable[[], Iterable[str]] | None = None,
        mountpoint: Path | None = None,
    ):
        self.bus_address = bus_address
        self.interface = interface
        self.fd_wrapper = fd_wrapper
        self.opener = opener or FileTransferPortal._open_path
        self.app_ids_provider = app_ids_provider or active_flatpak_app_ids
        self.mountpoint = mountpoint
        self.bus = None

    @staticmethod
    def _decode_path(value) -> Path:
        payload = bytes(value).rstrip(b"\0")
        return Path(payload.decode("utf-8", errors="surrogateescape"))

    def _connect(self):
        if self.interface is None or self.fd_wrapper is None:
            import dbus  # Optional SteamOS dependency; resolved lazily.

            self.bus = (
                dbus.bus.BusConnection(self.bus_address)
                if self.bus_address
                else dbus.SessionBus()
            )
            proxy = self.bus.get_object(PORTAL_BUS_NAME, PORTAL_OBJECT_PATH)
            self.interface = dbus.Interface(proxy, DOCUMENTS_INTERFACE)
            self.fd_wrapper = dbus.types.UnixFd
        if self.mountpoint is None:
            self.mountpoint = self._decode_path(
                self.interface.GetMountPoint()
            )

    @staticmethod
    def _path_from_uri(uri: str) -> Path | None:
        parsed = urlsplit(uri)
        if parsed.scheme != "file" or parsed.netloc or not parsed.path:
            return None
        return Path(unquote(parsed.path))

    def _export_batch(
        self,
        entries: list[tuple[int, Path, int]],
        *,
        is_directory: bool,
        app_ids: tuple[str, ...],
        output: list[str],
    ):
        if not entries:
            return
        primary_app = app_ids[0] if app_ids else ""
        permissions = ["read"] if primary_app else []
        flags = DOCUMENT_REUSE_EXISTING
        if is_directory:
            flags |= DOCUMENT_EXPORT_DIRECTORY
        descriptors = [entry[2] for entry in entries]
        doc_ids, extra = self.interface.AddFull(
            [self.fd_wrapper(descriptor) for descriptor in descriptors],
            flags,
            primary_app,
            permissions,
        )
        mountpoint_value = extra.get("mountpoint") if extra else None
        if mountpoint_value is not None:
            self.mountpoint = self._decode_path(mountpoint_value)
        mountpoint = self.mountpoint
        if mountpoint is None:
            return
        for (index, path, _descriptor), doc_id_value in zip(
            entries,
            doc_ids,
        ):
            doc_id = str(doc_id_value)
            if not doc_id:
                continue
            for app_id in app_ids[1:]:
                try:
                    self.interface.GrantPermissions(
                        doc_id,
                        app_id,
                        ["read"],
                    )
                except Exception as error:
                    LOGGER.info(
                        "Could not grant clipboard document %s to %s: %s",
                        doc_id,
                        app_id,
                        error,
                    )
            output[index] = (mountpoint / doc_id / path.name).as_uri()

    def export(self, file_uris: Iterable[str]) -> tuple[str, ...]:
        """Return portal-backed URIs, retaining originals that cannot export."""
        output = list(file_uris)
        if not output:
            return ()
        self._connect()
        app_ids = tuple(dict.fromkeys(
            app_id
            for app_id in self.app_ids_provider()
            if isinstance(app_id, str) and app_id
        ))
        opened: list[tuple[int, Path, int, bool]] = []
        try:
            for index, uri in enumerate(output):
                path = self._path_from_uri(uri)
                if path is None or not path.name:
                    continue
                try:
                    descriptor = self.opener(path)
                    is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
                    opened.append((index, path, descriptor, is_directory))
                except OSError as error:
                    LOGGER.info(
                        "Skipped a clipboard document %s: %s",
                        path,
                        error,
                    )
            for is_directory in (False, True):
                matching = [
                    (index, path, descriptor)
                    for index, path, descriptor, entry_is_directory in opened
                    if entry_is_directory == is_directory
                ]
                for offset in range(0, len(matching), PORTAL_FD_BATCH_SIZE):
                    batch = matching[offset:offset + PORTAL_FD_BATCH_SIZE]
                    try:
                        self._export_batch(
                            batch,
                            is_directory=is_directory,
                            app_ids=app_ids,
                            output=output,
                        )
                    except Exception as error:
                        LOGGER.warning(
                            "Could not export sandboxed clipboard files: %s",
                            error,
                        )
        finally:
            for _index, _path, descriptor, _is_directory in opened:
                os.close(descriptor)
        return tuple(output)

    def close(self):
        self.interface = None
        self.bus = None


class FileTransferPortal:
    """Own one replaceable xdg-desktop-portal file-transfer session."""

    def __init__(
        self,
        bus_address: str | None = None,
        *,
        interface=None,
        fd_wrapper: Callable[[int], object] | None = None,
        opener: Callable[[Path], int] | None = None,
    ):
        self.bus_address = bus_address
        self.interface = interface
        self.fd_wrapper = fd_wrapper
        self.opener = opener or self._open_path
        self.active_key: str | None = None

    def _connect(self):
        if self.interface is not None and self.fd_wrapper is not None:
            return
        import dbus  # Optional SteamOS dependency; resolved lazily.

        bus = (
            dbus.bus.BusConnection(self.bus_address)
            if self.bus_address
            else dbus.SessionBus()
        )
        proxy = bus.get_object(PORTAL_BUS_NAME, PORTAL_OBJECT_PATH)
        self.interface = dbus.Interface(proxy, PORTAL_INTERFACE)
        self.fd_wrapper = dbus.types.UnixFd

    @staticmethod
    def _local_paths(file_uris: Iterable[str]) -> tuple[Path, ...]:
        paths = []
        for uri in file_uris:
            parsed = urlsplit(uri)
            if parsed.scheme == "file" and not parsed.netloc:
                paths.append(Path(unquote(parsed.path)))
        return tuple(paths)

    @staticmethod
    def _open_path(path: Path) -> int:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK,
        )
        mode = os.fstat(descriptor).st_mode
        if stat.S_ISREG(mode) or stat.S_ISDIR(mode):
            return descriptor
        os.close(descriptor)
        raise OSError(f"Unsupported clipboard file type: {path}")

    def replace(self, file_uris: Iterable[str]) -> bytes | None:
        """Publish files under a fresh portal key and retire the old key."""
        paths = self._local_paths(file_uris)
        if not paths:
            self.clear()
            return None
        self._connect()
        key = str(self.interface.StartTransfer({
            "writable": False,
            "autostop": False,
        }))
        added = 0
        try:
            for offset in range(0, len(paths), PORTAL_FD_BATCH_SIZE):
                descriptors = []
                try:
                    for path in paths[
                        offset:offset + PORTAL_FD_BATCH_SIZE
                    ]:
                        try:
                            descriptors.append(self.opener(path))
                        except OSError as error:
                            LOGGER.info(
                                "Skipped a clipboard portal file %s: %s",
                                path,
                                error,
                            )
                    if descriptors:
                        self.interface.AddFiles(
                            key,
                            [self.fd_wrapper(fd) for fd in descriptors],
                            {},
                        )
                        added += len(descriptors)
                finally:
                    for descriptor in descriptors:
                        os.close(descriptor)
            if not added:
                self.interface.StopTransfer(key)
                self.clear()
                return None
        except Exception:
            self.interface.StopTransfer(key)
            raise

        previous_key = self.active_key
        self.active_key = key
        if previous_key and previous_key != key:
            self._stop(previous_key)
        return key.encode("utf-8")

    def _stop(self, key: str):
        try:
            self.interface.StopTransfer(key)
        except Exception as error:
            LOGGER.info(
                "Could not retire clipboard portal transfer %s: %s",
                key,
                error,
            )

    def clear(self):
        key = self.active_key
        self.active_key = None
        if key and self.interface is not None:
            self._stop(key)

    def close(self):
        self.clear()
