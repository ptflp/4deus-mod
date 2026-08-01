"""Immutable clipboard payload models shared by the X11 bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


MAX_FILE_URI_COUNT = 4096
PORTAL_FILE_TRANSFER_MIME = "application/vnd.portal.filetransfer"
PORTAL_FILES_MIME = "application/vnd.portal.files"
PLATFORM_FILE_MIME_TYPES = (
    PORTAL_FILE_TRANSFER_MIME,
    PORTAL_FILES_MIME,
)
LOGGER = logging.getLogger("4deus-nested-mouse")


def _normalize_file_uri(value: str) -> str | None:
    candidate = value.strip()
    if (
        not candidate
        or candidate.startswith("#")
        or "\0" in candidate
        or any(ord(character) < 0x20 for character in candidate)
    ):
        return None
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "file"
        or parsed.netloc.lower() not in ("", "localhost")
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
    ):
        return None
    return urlunsplit(("file", "", parsed.path, "", ""))


def normalize_file_uris(values: Iterable[str]) -> tuple[str, ...]:
    normalized = []
    seen = set()
    for value in values:
        if len(normalized) >= MAX_FILE_URI_COUNT:
            break
        uri = _normalize_file_uri(value) if isinstance(value, str) else None
        if uri is not None and uri not in seen:
            normalized.append(uri)
            seen.add(uri)
    return tuple(normalized)


def parse_file_uri_list(payload: bytes) -> tuple[str, ...]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return ()
    meaningful = [line for line in lines if line.strip()]
    if meaningful and meaningful[0].strip().lower() in ("copy", "cut"):
        meaningful = meaningful[1:]
    return normalize_file_uris(meaningful)


def encode_file_uri_list(file_uris: Iterable[str]) -> bytes:
    normalized = normalize_file_uris(file_uris)
    if not normalized:
        return b""
    return ("\r\n".join(normalized) + "\r\n").encode("utf-8")


def encode_gnome_copied_files(file_uris: Iterable[str]) -> bytes:
    normalized = normalize_file_uris(file_uris)
    if not normalized:
        return b""
    return ("copy\n" + "\n".join(normalized) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ClipboardContent:
    """The supported subset of one clipboard ownership."""

    text: str | None = None
    image_mime: str | None = None
    image: bytes | None = None
    file_uris: tuple[str, ...] = ()
    platform_file_formats: tuple[tuple[str, bytes], ...] = ()

    @property
    def byte_count(self) -> int:
        return (
            len(self.text.encode("utf-8")) if self.text is not None else 0
        ) + (len(self.image) if self.image is not None else 0) + len(
            encode_file_uri_list(self.file_uris)
        ) + sum(len(payload) for _mime, payload in self.platform_file_formats)

    @property
    def formats(self) -> tuple[str, ...]:
        formats = []
        if self.text is not None:
            formats.append("text/plain")
        if self.image is not None and self.image_mime is not None:
            formats.append(self.image_mime)
        if self.file_uris:
            formats.append("text/uri-list")
        formats.extend(mime for mime, _payload in self.platform_file_formats)
        return tuple(formats)

    @property
    def available(self) -> bool:
        return bool(self.formats)

    def without_files(self) -> ClipboardContent:
        if not self.file_uris and not self.platform_file_formats:
            return self
        return ClipboardContent(
            text=self.text,
            image_mime=self.image_mime,
            image=self.image,
        )


def normalize_content(
    content: ClipboardContent,
    *,
    image_mimes: Iterable[str],
    max_bytes: int,
    max_text_bytes: int,
    max_file_list_bytes: int,
    platform_file_mimes: Iterable[str] = (),
) -> ClipboardContent:
    text = content.text if isinstance(content.text, str) else None
    if text is not None and len(text.encode("utf-8")) > max_text_bytes:
        LOGGER.warning(
            "Clipboard text exceeds the %s-byte sharing limit",
            max_text_bytes,
        )
        text = None
    image = content.image if isinstance(content.image, bytes) else None
    image_mime = (
        content.image_mime
        if content.image_mime in image_mimes
        else None
    )
    if image is not None and len(image) > max_bytes:
        LOGGER.warning("Clipboard image exceeds the %s-byte sharing limit", max_bytes)
        image = None
    if not image or image_mime is None:
        image = None
        image_mime = None
    file_uris = normalize_file_uris(content.file_uris)
    if file_uris and len(encode_file_uri_list(file_uris)) > max_file_list_bytes:
        LOGGER.warning(
            "Clipboard file list exceeds the %s-byte sharing limit",
            max_file_list_bytes,
        )
        file_uris = ()
    allowed_platform_mimes = set(platform_file_mimes)
    platform_payloads = {
        mime: payload
        for mime, payload in content.platform_file_formats
        if (
            mime in allowed_platform_mimes
            and isinstance(payload, bytes)
            and 0 < len(payload) <= max_file_list_bytes
        )
    }
    return ClipboardContent(
        text=text,
        image_mime=image_mime,
        image=image,
        file_uris=file_uris,
        platform_file_formats=tuple(sorted(platform_payloads.items())),
    )


@dataclass
class PendingClipboardContent:
    text: str | None = None
    image_mime: str | None = None
    image: bytes | None = None
    file_uris: tuple[str, ...] = ()
    platform_file_formats: dict[str, bytes] = field(default_factory=dict)

    def freeze(self) -> ClipboardContent:
        return ClipboardContent(
            text=self.text,
            image_mime=self.image_mime,
            image=self.image,
            file_uris=self.file_uris,
            platform_file_formats=tuple(sorted(
                self.platform_file_formats.items()
            )),
        )
