from __future__ import annotations

import io
import math
import random
import struct
import zlib
from collections import deque

# TempleOS color indices used in GodDoodle.HC
BLACK = 0
RED = 4
LTGRAY = 7
DKGRAY = 8
WHITE = 15

FILL_COLORS = (BLACK, DKGRAY, LTGRAY, WHITE)

# Standard 16-color TempleOS VGA palette (RGB)
TEMPLE_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),        # 0: BLACK
    (0, 0, 170),      # 1: BLUE
    (0, 170, 0),      # 2: GREEN
    (0, 170, 170),    # 3: CYAN
    (170, 0, 0),      # 4: RED
    (170, 0, 170),    # 5: PURPLE
    (170, 85, 0),     # 6: BROWN
    (170, 170, 170),  # 7: LTGRAY
    (85, 85, 85),     # 8: DKGRAY
    (85, 85, 255),    # 9: LTBLUE
    (85, 255, 85),    # 10: LTGREEN
    (85, 255, 255),   # 11: LTCYAN
    (255, 85, 85),    # 12: LTRED
    (255, 85, 255),   # 13: LTPURPLE
    (255, 255, 85),   # 14: YELLOW
    (255, 255, 255),  # 15: WHITE
)


class _DoodleFifo:
    """Port of god.doodle_fifo, GodDoodleHexIns, and GodDoodleBits."""

    def __init__(self, hex_seed: str | None = None):
        self.queue: deque[int] = deque()
        if hex_seed:
            for ch in hex_seed:
                if ch in "0123456789abcdefABCDEF":
                    val = int(ch, 16)
                    # GodDoodleHexIns pushes rev_bits_table[nibble] >> 4 LSB-first,
                    # which places the MSB at the front of the FIFO.
                    for shift in (3, 2, 1, 0):
                        self.queue.append((val >> shift) & 1)

    def bits(self, num_bits: int) -> int:
        res = 0
        for _ in range(num_bits):
            b = self.queue.popleft() if self.queue else random.getrandbits(1)
            res = (res << 1) | b
        return res


def _draw_line(
    grid: bytearray,
    w: int,
    h: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: int,
) -> None:
    """Port of GrLine3 using 8-connected Bresenham line drawing."""
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            grid[y0 * w + x0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_border(
    grid: bytearray,
    w: int,
    h: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: int,
) -> None:
    """Port of GrBorder."""
    _draw_line(grid, w, h, x1, y1, x2, y1, color)
    _draw_line(grid, w, h, x2, y1, x2, y2, color)
    _draw_line(grid, w, h, x2, y2, x1, y2, color)
    _draw_line(grid, w, h, x1, y2, x1, y1, color)


def _draw_ellipse(
    grid: bytearray,
    w: int,
    h: int,
    cx: int,
    cy: int,
    rx: int,
    ry: int,
    color: int,
) -> None:
    """Port of GrEllipse3 and GrCircle3 using connected line segments."""
    rx = abs(int(rx))
    ry = abs(int(ry))
    if rx == 0 and ry == 0:
        if 0 <= cx < w and 0 <= cy < h:
            grid[cy * w + cx] = color
        return

    steps = max(64, int(2.0 * math.pi * max(rx, ry) / 4.0))
    prev_x = int(round(cx + rx))
    prev_y = int(round(cy))
    for i in range(1, steps + 1):
        theta = (2.0 * math.pi * i) / steps
        cur_x = int(round(cx + rx * math.cos(theta)))
        cur_y = int(round(cy + ry * math.sin(theta)))
        _draw_line(grid, w, h, prev_x, prev_y, cur_x, cur_y, color)
        prev_x, prev_y = cur_x, cur_y


def _flood_fill(
    grid: bytearray,
    w: int,
    h: int,
    x: int,
    y: int,
    new_color: int,
) -> None:
    """Port of GrFloodFill3 (4-connected flood fill)."""
    if not (0 <= x < w and 0 <= y < h):
        return
    start_idx = y * w + x
    target_color = grid[start_idx]
    if target_color == new_color:
        return

    grid[start_idx] = new_color
    q = deque([start_idx])
    while q:
        idx = q.popleft()
        py, px = divmod(idx, w)
        if px > 0 and grid[idx - 1] == target_color:
            grid[idx - 1] = new_color
            q.append(idx - 1)
        if px + 1 < w and grid[idx + 1] == target_color:
            grid[idx + 1] = new_color
            q.append(idx + 1)
        if py > 0 and grid[idx - w] == target_color:
            grid[idx - w] = new_color
            q.append(idx - w)
        if py + 1 < h and grid[idx + w] == target_color:
            grid[idx + w] = new_color
            q.append(idx + w)


def _god_doodle_smooth(grid: bytearray, w: int, h: int, num: int) -> bytearray:
    """
    Sliding-window port of GodDoodleSmooth(I64 num).
    Computes the dominant color in the (2*num + 1) x (2*num + 1) neighborhood
    around each pixel, breaking ties in ascending palette index order.
    """
    if num <= 0:
        return bytearray(grid)

    out = bytearray(w * h)
    col0 = [0] * w
    col4 = [0] * w
    col7 = [0] * w
    col8 = [0] * w
    col15 = [0] * w

    for yy in range(min(h, num + 1)):
        row = grid[yy * w : (yy + 1) * w]
        for x, v in enumerate(row):
            if v == 15:
                col15[x] += 1
            elif v == 8:
                col8[x] += 1
            elif v == 7:
                col7[x] += 1
            elif v == 0:
                col0[x] += 1
            elif v == 4:
                col4[x] += 1

    w_limit = w - num
    for y in range(h):
        if y > 0:
            y_add = y + num
            if y_add < h:
                row_add = grid[y_add * w : (y_add + 1) * w]
                for x, v in enumerate(row_add):
                    if v == 15:
                        col15[x] += 1
                    elif v == 8:
                        col8[x] += 1
                    elif v == 7:
                        col7[x] += 1
                    elif v == 0:
                        col0[x] += 1
                    elif v == 4:
                        col4[x] += 1
            y_rem = y - num - 1
            if y_rem >= 0:
                row_rem = grid[y_rem * w : (y_rem + 1) * w]
                for x, v in enumerate(row_rem):
                    if v == 15:
                        col15[x] -= 1
                    elif v == 8:
                        col8[x] -= 1
                    elif v == 7:
                        col7[x] -= 1
                    elif v == 0:
                        col0[x] -= 1
                    elif v == 4:
                        col4[x] -= 1

        c0 = sum(col0[: num + 1])
        c4 = sum(col4[: num + 1])
        c7 = sum(col7[: num + 1])
        c8 = sum(col8[: num + 1])
        c15 = sum(col15[: num + 1])

        half = ((2 * num + 1) * (min(h - 1, y + num) - max(0, y - num) + 1)) // 2
        row_off = y * w

        for x in range(w):
            if x > 0:
                if x < w_limit:
                    x_add = x + num
                    c15 += col15[x_add]
                    c8 += col8[x_add]
                    c7 += col7[x_add]
                    c0 += col0[x_add]
                    c4 += col4[x_add]
                if x > num:
                    x_rem = x - num - 1
                    c15 -= col15[x_rem]
                    c8 -= col8[x_rem]
                    c7 -= col7[x_rem]
                    c0 -= col0[x_rem]
                    c4 -= col4[x_rem]

            if c15 > half:
                out[row_off + x] = 15
            elif c8 > half:
                out[row_off + x] = 8
            elif c7 > half:
                out[row_off + x] = 7
            elif c0 > half:
                out[row_off + x] = 0
            else:
                best = 0
                best_cnt = c0
                if c4 > best_cnt:
                    best = 4
                    best_cnt = c4
                if c7 > best_cnt:
                    best = 7
                    best_cnt = c7
                if c8 > best_cnt:
                    best = 8
                    best_cnt = c8
                if c15 > best_cnt:
                    best = 15
                out[row_off + x] = best

    return out


def _encode_png_paletted(grid: bytearray, w: int, h: int) -> bytes:
    """Encodes an 8-bit indexed PNG using the 16-color TempleOS palette."""

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    out = bytearray(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)
    out.extend(make_chunk(b"IHDR", ihdr))

    plte = bytearray()
    for r, g, b in TEMPLE_PALETTE:
        plte.extend((r, g, b))
    out.extend(make_chunk(b"PLTE", bytes(plte)))

    raw_scanlines = bytearray()
    for y in range(h):
        raw_scanlines.append(0)
        raw_scanlines.extend(grid[y * w : (y + 1) * w])
    compressed = zlib.compress(bytes(raw_scanlines), level=6)
    out.extend(make_chunk(b"IDAT", compressed))

    out.extend(make_chunk(b"IEND", b""))
    return bytes(out)


def generate_goddoodle_image(
    width: int = 640,
    height: int = 480,
    smooth: int = 3,
    hex_seed: str | None = None,
) -> io.BytesIO:
    """
    Port of GodDoodleSprite() from GodDoodle.HC.
    Returns an in-memory PNG BytesIO stream.
    """
    fifo = _DoodleFifo(hex_seed)
    grid = bytearray([WHITE] * (width * height))

    for _ in range(3):
        for _ in range(29):
            kind = fifo.bits(3)
            if kind == 0:
                cx = int((width - 1) * fifo.bits(5) / 15.5 - width / 2)
                cy = int((height - 1) * fifo.bits(5) / 15.5 - height / 2)
                rx = int((width - 1) * fifo.bits(5) / 15.5)
                ry = int((height - 1) * fifo.bits(5) / 15.5)
                _draw_ellipse(grid, width, height, cx, cy, rx, ry, RED)
            elif kind == 1:
                cx = int((width - 1) * fifo.bits(5) / 15.5 - width / 2)
                cy = int((height - 1) * fifo.bits(5) / 15.5 - height / 2)
                r = int((width - 1) * fifo.bits(5) / 15.5)
                _draw_ellipse(grid, width, height, cx, cy, r, r, RED)
            elif kind == 2:
                x1 = int((width - 1) * fifo.bits(5) / 15.5 - width / 2)
                y1 = int((height - 1) * fifo.bits(5) / 15.5 - height / 2)
                x2 = int((width - 1) * fifo.bits(5) / 15.5)
                y2 = int((height - 1) * fifo.bits(5) / 15.5)
                _draw_border(grid, width, height, x1, y1, x2, y2, RED)
            else:
                x1 = (width - 1) * fifo.bits(4) // 15
                y1 = (height - 1) * fifo.bits(4) // 15
                x2 = (width - 1) * fifo.bits(4) // 15
                y2 = (height - 1) * fifo.bits(4) // 15
                _draw_line(grid, width, height, x1, y1, x2, y2, RED)

        for _ in range(6):
            x = (width - 1) * fifo.bits(5) // 31 + width // 64
            y = (height - 1) * fifo.bits(5) // 31 + height // 64
            color = FILL_COLORS[fifo.bits(2)]
            _flood_fill(grid, width, height, x, y, color)

        if smooth > 0:
            grid = _god_doodle_smooth(grid, width, height, smooth)

    png_bytes = _encode_png_paletted(grid, width, height)
    return io.BytesIO(png_bytes)