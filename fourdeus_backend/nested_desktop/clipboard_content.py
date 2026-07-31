"""Immutable clipboard payload models shared by the X11 bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


MAX_FILE_URI_COUNT = 4096


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

    @property
    def byte_count(self) -> int:
        return (
            len(self.text.encode("utf-8")) if self.text is not None else 0
        ) + (len(self.image) if self.image is not None else 0) + len(
            encode_file_uri_list(self.file_uris)
        )

    @property
    def formats(self) -> tuple[str, ...]:
        formats = []
        if self.text is not None:
            formats.append("text/plain")
        if self.image is not None and self.image_mime is not None:
            formats.append(self.image_mime)
        if self.file_uris:
            formats.append("text/uri-list")
        return tuple(formats)

    @property
    def available(self) -> bool:
        return bool(self.formats)

    def without_files(self) -> ClipboardContent:
        if not self.file_uris:
            return self
        return ClipboardContent(
            text=self.text,
            image_mime=self.image_mime,
            image=self.image,
        )


@dataclass
class PendingClipboardContent:
    text: str | None = None
    image_mime: str | None = None
    image: bytes | None = None
    file_uris: tuple[str, ...] = ()

    def freeze(self) -> ClipboardContent:
        return ClipboardContent(
            text=self.text,
            image_mime=self.image_mime,
            image=self.image,
            file_uris=self.file_uris,
        )
