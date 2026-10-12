"""Read Steam's binary shortcut metadata without changing it."""

import struct


def read_shortcuts(data: bytes) -> list[dict]:
    offset = 0

    def string() -> str:
        nonlocal offset
        end = data.index(b"\0", offset)
        value = data[offset:end].decode("utf-8", errors="replace")
        offset = end + 1
        return value

    def object_at(depth: int = 0) -> dict:
        nonlocal offset
        if depth > 16:
            raise ValueError("Shortcut metadata nesting is too deep")
        result = {}
        while offset < len(data):
            kind = data[offset]
            offset += 1
            if kind == 8:
                return result
            name = string().lower()
            if kind == 0:
                value = object_at(depth + 1)
            elif kind == 1:
                value = string()
            elif kind == 2:
                value = struct.unpack_from("<I", data, offset)[0]
                offset += 4
            else:
                raise ValueError("Unsupported shortcut metadata field")
            result[name] = value
        raise ValueError("Truncated shortcut metadata")

    shortcuts = object_at().get("shortcuts", {})
    return [value for value in shortcuts.values() if isinstance(value, dict)]
