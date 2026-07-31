"""Software cursor rendering for the Nested Desktop framebuffer."""

from __future__ import annotations

import ctypes
import ctypes.util
import time
from typing import Sequence

from .constants import (
    CURSOR_IMAGE_REFRESH_INTERVAL, CURSOR_OUTLINE_PIXEL,
    CURSOR_OUTLINE_RADIUS,
)
from .models import CursorSnapshot, NestedDesktopSession, PointerUpdate
from .x11 import X11Connection


class _XFixesCursorImage(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_ushort),
        ("height", ctypes.c_ushort),
        ("xhot", ctypes.c_ushort),
        ("yhot", ctypes.c_ushort),
        ("cursor_serial", ctypes.c_ulong),
        ("pixels", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _XSetWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("background_pixmap", ctypes.c_ulong),
        ("background_pixel", ctypes.c_ulong),
        ("border_pixmap", ctypes.c_ulong),
        ("border_pixel", ctypes.c_ulong),
        ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int),
        ("event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int),
        ("colormap", ctypes.c_ulong),
        ("cursor", ctypes.c_ulong),
    ]

class _XImage(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("xoffset", ctypes.c_int),
        ("format", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("byte_order", ctypes.c_int),
        ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int),
        ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int),
        ("red_mask", ctypes.c_ulong),
        ("green_mask", ctypes.c_ulong),
        ("blue_mask", ctypes.c_ulong),
        ("obdata", ctypes.c_void_p),
    ]

def cursor_alpha_mask(
    pixels: Sequence[int],
    width: int,
    height: int,
) -> bytes:
    row_bytes = (width + 7) // 8
    mask = bytearray(row_bytes * height)
    for y in range(height):
        row_offset = y * width
        mask_offset = y * row_bytes
        for x in range(width):
            if (int(pixels[row_offset + x]) >> 24) & 0xFF:
                mask[mask_offset + (x // 8)] |= 1 << (x % 8)
    return bytes(mask)

def outlined_cursor_snapshot(
    snapshot: CursorSnapshot,
    radius: int = CURSOR_OUTLINE_RADIUS,
) -> CursorSnapshot:
    """Adds a light outline while preserving the cursor's exact hotspot."""
    if radius <= 0:
        return snapshot

    width = snapshot.width + (radius * 2)
    height = snapshot.height + (radius * 2)
    pixels = [0] * (width * height)
    for source_y in range(snapshot.height):
        source_row = source_y * snapshot.width
        for source_x in range(snapshot.width):
            source_pixel = snapshot.pixels[source_row + source_x]
            if not ((source_pixel >> 24) & 0xFF):
                continue
            center_x = source_x + radius
            center_y = source_y + radius
            for outline_y in range(
                center_y - radius,
                center_y + radius + 1,
            ):
                outline_row = outline_y * width
                for outline_x in range(
                    center_x - radius,
                    center_x + radius + 1,
                ):
                    pixels[outline_row + outline_x] = (
                        CURSOR_OUTLINE_PIXEL
                    )

    for source_y in range(snapshot.height):
        source_row = source_y * snapshot.width
        target_row = (source_y + radius) * width + radius
        for source_x in range(snapshot.width):
            source_pixel = snapshot.pixels[source_row + source_x]
            if (source_pixel >> 24) & 0xFF:
                pixels[target_row + source_x] = source_pixel

    return CursorSnapshot(
        x=snapshot.x,
        y=snapshot.y,
        width=width,
        height=height,
        xhot=snapshot.xhot + radius,
        yhot=snapshot.yhot + radius,
        serial=snapshot.serial,
        pixels=tuple(pixels),
    )

class NestedDesktopCursorOverlay:
    """Draws KWin's cursor into the nested framebuffer on demand."""

    CW_OVERRIDE_REDIRECT = 1 << 9
    CW_SAVE_UNDER = 1 << 10
    SHAPE_BOUNDING = 0
    SHAPE_INPUT = 2
    SHAPE_SET = 0
    Z_PIXMAP = 2

    def __init__(self, session: NestedDesktopSession):
        self.connection = X11Connection(
            session.display,
            session.xauthority,
        )
        self.x11 = self.connection.x11
        self.display = self.connection.display
        self.root = self.connection.root
        self.xfixes = ctypes.CDLL(
            ctypes.util.find_library("Xfixes") or "libXfixes.so.3"
        )
        self.xext = ctypes.CDLL(
            ctypes.util.find_library("Xext") or "libXext.so.6"
        )
        self._configure_libraries()
        self.screen = self.x11.XDefaultScreen(self.display)
        self.visual = self.x11.XDefaultVisual(
            self.display,
            self.screen,
        )
        self.depth = self.x11.XDefaultDepth(
            self.display,
            self.screen,
        )
        self.screen_width = self.x11.XDisplayWidth(
            self.display,
            self.screen,
        )
        self.screen_height = self.x11.XDisplayHeight(
            self.display,
            self.screen,
        )
        self.window = 0
        self.gc = None
        self.visible = False
        self.cursor_serial: int | None = None
        self.cursor_width = 1
        self.cursor_height = 1
        self.cursor_xhot = 0
        self.cursor_yhot = 0
        self.pointer_x = 0.0
        self.pointer_y = 0.0
        self.position_primed = False
        self.window_position: tuple[int, int] | None = None
        self.rendered_snapshot: CursorSnapshot | None = None
        self.next_image_refresh = 0.0

    def _configure_libraries(self):
        pointer = ctypes.c_void_p
        window = ctypes.c_ulong
        self.x11.XDefaultScreen.argtypes = [pointer]
        self.x11.XDefaultScreen.restype = ctypes.c_int
        self.x11.XDefaultVisual.argtypes = [pointer, ctypes.c_int]
        self.x11.XDefaultVisual.restype = pointer
        self.x11.XDefaultDepth.argtypes = [pointer, ctypes.c_int]
        self.x11.XDefaultDepth.restype = ctypes.c_int
        self.x11.XDisplayWidth.argtypes = [pointer, ctypes.c_int]
        self.x11.XDisplayWidth.restype = ctypes.c_int
        self.x11.XDisplayHeight.argtypes = [pointer, ctypes.c_int]
        self.x11.XDisplayHeight.restype = ctypes.c_int
        self.x11.XCreateSimpleWindow.argtypes = [
            pointer,
            window,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.x11.XCreateSimpleWindow.restype = window
        self.x11.XChangeWindowAttributes.argtypes = [
            pointer,
            window,
            ctypes.c_ulong,
            ctypes.POINTER(_XSetWindowAttributes),
        ]
        self.x11.XCreateGC.argtypes = [
            pointer,
            window,
            ctypes.c_ulong,
            pointer,
        ]
        self.x11.XCreateGC.restype = pointer
        self.x11.XFreeGC.argtypes = [pointer, pointer]
        self.x11.XCreateImage.argtypes = [
            pointer,
            pointer,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            pointer,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.x11.XCreateImage.restype = ctypes.POINTER(_XImage)
        self.x11.XPutImage.argtypes = [
            pointer,
            window,
            pointer,
            ctypes.POINTER(_XImage),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self.x11.XCreateBitmapFromData.argtypes = [
            pointer,
            window,
            pointer,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self.x11.XCreateBitmapFromData.restype = window
        self.x11.XFreePixmap.argtypes = [pointer, window]
        self.x11.XMoveWindow.argtypes = [
            pointer,
            window,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.x11.XResizeWindow.argtypes = [
            pointer,
            window,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self.x11.XMapRaised.argtypes = [pointer, window]
        self.x11.XUnmapWindow.argtypes = [pointer, window]
        self.x11.XDestroyWindow.argtypes = [pointer, window]

        self.xfixes.XFixesGetCursorImage.argtypes = [pointer]
        self.xfixes.XFixesGetCursorImage.restype = ctypes.POINTER(
            _XFixesCursorImage
        )
        self.xfixes.XFixesCreateRegion.argtypes = [
            pointer,
            pointer,
            ctypes.c_int,
        ]
        self.xfixes.XFixesCreateRegion.restype = ctypes.c_ulong
        self.xfixes.XFixesSetWindowShapeRegion.argtypes = [
            pointer,
            window,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self.xfixes.XFixesDestroyRegion.argtypes = [
            pointer,
            ctypes.c_ulong,
        ]
        self.xext.XShapeCombineMask.argtypes = [
            pointer,
            window,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            window,
            ctypes.c_int,
        ]

    def _snapshot(self) -> CursorSnapshot:
        image = self.xfixes.XFixesGetCursorImage(self.display)
        if not image:
            raise RuntimeError("Cannot read the Nested Desktop cursor")
        try:
            value = image.contents
            count = value.width * value.height
            return CursorSnapshot(
                x=int(value.x),
                y=int(value.y),
                width=int(value.width),
                height=int(value.height),
                xhot=int(value.xhot),
                yhot=int(value.yhot),
                serial=int(value.cursor_serial),
                pixels=tuple(
                    int(value.pixels[index]) & 0xFFFFFFFF
                    for index in range(count)
                ),
            )
        finally:
            self.x11.XFree(image)

    def _ensure_window(self, snapshot: CursorSnapshot):
        if self.window:
            if (
                snapshot.width != self.cursor_width
                or snapshot.height != self.cursor_height
            ):
                self.x11.XResizeWindow(
                    self.display,
                    self.window,
                    snapshot.width,
                    snapshot.height,
                )
            return
        self.window = self.x11.XCreateSimpleWindow(
            self.display,
            self.root,
            0,
            0,
            snapshot.width,
            snapshot.height,
            0,
            0,
            0,
        )
        if not self.window:
            raise RuntimeError("Cannot create the cursor overlay window")
        attributes = _XSetWindowAttributes()
        attributes.override_redirect = 1
        attributes.save_under = 1
        self.x11.XChangeWindowAttributes(
            self.display,
            self.window,
            self.CW_OVERRIDE_REDIRECT | self.CW_SAVE_UNDER,
            ctypes.byref(attributes),
        )
        self.gc = self.x11.XCreateGC(
            self.display,
            self.window,
            0,
            None,
        )
        if not self.gc:
            raise RuntimeError("Cannot create the cursor overlay GC")
        empty_region = self.xfixes.XFixesCreateRegion(
            self.display,
            None,
            0,
        )
        self.xfixes.XFixesSetWindowShapeRegion(
            self.display,
            self.window,
            self.SHAPE_INPUT,
            0,
            0,
            empty_region,
        )
        self.xfixes.XFixesDestroyRegion(
            self.display,
            empty_region,
        )

    def _draw(self, snapshot: CursorSnapshot):
        self._ensure_window(snapshot)
        image = self.x11.XCreateImage(
            self.display,
            self.visual,
            self.depth,
            self.Z_PIXMAP,
            0,
            None,
            snapshot.width,
            snapshot.height,
            32,
            0,
        )
        if not image:
            raise RuntimeError("Cannot create the cursor overlay image")
        try:
            if image.contents.bits_per_pixel != 32:
                raise RuntimeError(
                    "Unsupported Nested Desktop X image format"
                )
            image_bytes = ctypes.create_string_buffer(
                image.contents.bytes_per_line * snapshot.height
            )
            image.contents.data = ctypes.addressof(image_bytes)
            for y in range(snapshot.height):
                row = y * image.contents.bytes_per_line
                source_row = y * snapshot.width
                for x in range(snapshot.width):
                    pixel = snapshot.pixels[source_row + x] & 0xFFFFFF
                    offset = row + (x * 4)
                    image_bytes[offset : offset + 4] = pixel.to_bytes(
                        4,
                        "little",
                    )
            self.x11.XPutImage(
                self.display,
                self.window,
                self.gc,
                image,
                0,
                0,
                0,
                0,
                snapshot.width,
                snapshot.height,
            )
            self.x11.XFlush(self.display)
        finally:
            image.contents.data = None
            self.x11.XFree(image)

        mask_bytes = ctypes.create_string_buffer(
            cursor_alpha_mask(
                snapshot.pixels,
                snapshot.width,
                snapshot.height,
            )
        )
        mask = self.x11.XCreateBitmapFromData(
            self.display,
            self.window,
            ctypes.addressof(mask_bytes),
            snapshot.width,
            snapshot.height,
        )
        if not mask:
            raise RuntimeError("Cannot create the cursor overlay mask")
        try:
            self.xext.XShapeCombineMask(
                self.display,
                self.window,
                self.SHAPE_BOUNDING,
                0,
                0,
                mask,
                self.SHAPE_SET,
            )
        finally:
            self.x11.XFreePixmap(self.display, mask)

        self.cursor_serial = snapshot.serial
        self.cursor_width = snapshot.width
        self.cursor_height = snapshot.height
        self.cursor_xhot = snapshot.xhot
        self.cursor_yhot = snapshot.yhot
        self.rendered_snapshot = snapshot

    def _move(self):
        if not self.window:
            return
        position = (
            round(self.pointer_x) - self.cursor_xhot,
            round(self.pointer_y) - self.cursor_yhot,
        )
        if position == self.window_position:
            return
        self.x11.XMoveWindow(
            self.display,
            self.window,
            position[0],
            position[1],
        )
        self.x11.XFlush(self.display)
        self.window_position = position

    def refresh(
        self,
        force_image: bool = False,
        sync_position: bool = True,
    ):
        now = time.monotonic()
        if not force_image and now < self.next_image_refresh:
            return
        snapshot = self._snapshot()
        if sync_position or not self.position_primed:
            self.pointer_x = snapshot.x
            self.pointer_y = snapshot.y
            self.position_primed = True
        has_visible_pixels = any(
            (pixel >> 24) & 0xFF for pixel in snapshot.pixels
        )
        if (
            has_visible_pixels
            and (
                force_image
                or snapshot.serial != self.cursor_serial
                or (
                    snapshot.width + (CURSOR_OUTLINE_RADIUS * 2)
                    != self.cursor_width
                )
                or (
                    snapshot.height + (CURSOR_OUTLINE_RADIUS * 2)
                    != self.cursor_height
                )
            )
        ):
            self._draw(outlined_cursor_snapshot(snapshot))
        elif has_visible_pixels:
            self.cursor_xhot = snapshot.xhot + CURSOR_OUTLINE_RADIUS
            self.cursor_yhot = snapshot.yhot + CURSOR_OUTLINE_RADIUS
        elif self.cursor_serial is None:
            raise RuntimeError(
                "Nested Desktop returned an empty cursor image"
            )
        self._move()
        self.next_image_refresh = (
            now + CURSOR_IMAGE_REFRESH_INTERVAL
        )

    def prime(self):
        if self.visible:
            return
        self.refresh(
            force_image=self.cursor_serial is None,
            sync_position=True,
        )

    def show(self):
        if self.visible:
            # XFixes can lag behind EIS while pointer forwarding is active.
            # Keep following the injected updates instead of snapping back to
            # a stale compositor position on every image refresh.
            self.refresh(sync_position=False)
            return
        # The pointer may have moved while the overlay was hidden. Rebase once
        # when it becomes visible, before local relative tracking resumes.
        self.refresh(
            force_image=self.cursor_serial is None,
            sync_position=True,
        )
        self.x11.XMapRaised(self.display, self.window)
        self.x11.XFlush(self.display)
        self.visible = True
        # Mapping an override-redirect window may clear its backing pixels.
        # Repaint the cached image once after the map; ongoing pointer motion
        # only moves the window and never pays this cost.
        if self.rendered_snapshot is not None:
            self._draw(self.rendered_snapshot)

    def hide(self):
        if not self.visible or not self.window:
            return
        self.x11.XUnmapWindow(self.display, self.window)
        self.x11.XFlush(self.display)
        self.visible = False

    def apply(self, update: PointerUpdate):
        if not self.visible:
            return
        moved = False
        if update.absolute_x is not None:
            self.pointer_x = update.absolute_x
            moved = True
        elif update.dx:
            self.pointer_x += update.dx
            moved = True
        if update.absolute_y is not None:
            self.pointer_y = update.absolute_y
            moved = True
        elif update.dy:
            self.pointer_y += update.dy
            moved = True
        if not moved:
            return
        self.pointer_x = max(
            0.0,
            min(float(self.screen_width - 1), self.pointer_x),
        )
        self.pointer_y = max(
            0.0,
            min(float(self.screen_height - 1), self.pointer_y),
        )
        self._move()

    def close(self):
        display = getattr(self, "display", None)
        if display:
            if self.gc:
                self.x11.XFreeGC(display, self.gc)
                self.gc = None
            if self.window:
                self.x11.XDestroyWindow(display, self.window)
                self.window = 0
            self.x11.XFlush(display)
        self.visible = False
        self.rendered_snapshot = None
        self.connection.close()
        self.display = None
