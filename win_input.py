"""Minimal outbound-only Windows input simulation.

This module intentionally uses the documented Windows SendInput API instead
of third-party packages that install global keyboard or mouse hooks. The app
only needs to send configured commands to the foreground game window.
"""

import ctypes
import re
import time
from ctypes import wintypes


if not hasattr(ctypes, "windll"):
    raise RuntimeError("Kabutopz Voice Protocol input requires Windows.")


ULONG_PTR = (
    ctypes.c_ulonglong
    if ctypes.sizeof(ctypes.c_void_p) == 8
    else ctypes.c_ulong
)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT_DATA(ctypes.Union):
    _fields_ = (
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = (("type", wintypes.DWORD), ("data", INPUT_DATA))


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


_VK_NAMES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "caps lock": 0x14,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "page up": 0x21,
    "page down": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "left windows": 0x5B,
    "right windows": 0x5C,
    "num multiply": 0x6A,
    "num plus": 0x6B,
    "num minus": 0x6D,
    "num decimal": 0x6E,
    "num divide": 0x6F,
    "num lock": 0x90,
    "scroll lock": 0x91,
    "left shift": 0xA0,
    "right shift": 0xA1,
    "left ctrl": 0xA2,
    "right ctrl": 0xA3,
    "left control": 0xA2,
    "right control": 0xA3,
    "left alt": 0xA4,
    "right alt": 0xA5,
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}

for number in range(10):
    _VK_NAMES[str(number)] = 0x30 + number
    _VK_NAMES[f"num {number}"] = 0x60 + number
    _VK_NAMES[f"numpad {number}"] = 0x60 + number

for letter in "abcdefghijklmnopqrstuvwxyz":
    _VK_NAMES[letter] = ord(letter.upper())

for number in range(1, 25):
    _VK_NAMES[f"f{number}"] = 0x6F + number


_EXTENDED_KEYS = {
    "right alt",
    "right ctrl",
    "right control",
    "left windows",
    "right windows",
    "insert",
    "delete",
    "home",
    "end",
    "page up",
    "page down",
    "left",
    "right",
    "up",
    "down",
    "num divide",
    "num lock",
}


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = (
    wintypes.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
)
_user32.SendInput.restype = wintypes.UINT
_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT


def _normalize_key_name(name):
    normalized = re.sub(r"\s+", " ", str(name).strip().lower())
    aliases = {
        "lalt": "left alt",
        "ralt": "right alt",
        "lctrl": "left ctrl",
        "rctrl": "right ctrl",
        "lshift": "left shift",
        "rshift": "right shift",
        "pgup": "page up",
        "pgdn": "page down",
        "del": "delete",
        "ins": "insert",
        "win": "left windows",
        "windows": "left windows",
    }
    return aliases.get(normalized, normalized)


def resolve_key(name):
    """Return ``(virtual_key, is_extended)`` for a configured key name."""
    normalized = _normalize_key_name(name)
    try:
        return _VK_NAMES[normalized], normalized in _EXTENDED_KEYS
    except KeyError as exc:
        raise ValueError(f"Unsupported key name: {name}") from exc


def _send(packet):
    if _user32.SendInput(1, ctypes.byref(packet), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def _key_event(name, key_up=False):
    virtual_key, extended = resolve_key(name)
    scan_code = _user32.MapVirtualKeyW(virtual_key, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if key_up:
        flags |= KEYEVENTF_KEYUP
    _send(
        INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=0,
                wScan=scan_code,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            ),
        )
    )


def _key_parts(keybind):
    parts = [_normalize_key_name(part) for part in str(keybind).split("+")]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("Keybind cannot be empty.")
    for part in parts:
        resolve_key(part)
    return parts


def press_keybind(keybind):
    parts = _key_parts(keybind)
    pressed = []
    try:
        for part in parts:
            _key_event(part)
            pressed.append(part)
    except Exception:
        for part in reversed(pressed):
            _key_event(part, key_up=True)
        raise
    return parts


def release_keybind(parts):
    for part in reversed(parts):
        _key_event(part, key_up=True)


def tap_keybind(keybind, tap_seconds=0.04):
    parts = press_keybind(keybind)
    try:
        time.sleep(tap_seconds)
    finally:
        release_keybind(parts)


def hold_keybind(keybind, hold_seconds):
    parts = press_keybind(keybind)
    try:
        time.sleep(float(hold_seconds))
    finally:
        release_keybind(parts)


def _mouse_event(flags, data=0):
    _send(
        INPUT(
            type=INPUT_MOUSE,
            mi=MOUSEINPUT(
                dx=0,
                dy=0,
                mouseData=data,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            ),
        )
    )


def click_mouse(button):
    normalized = _normalize_key_name(button)
    if normalized == "left":
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    elif normalized == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    else:
        raise ValueError(f"Unsupported mouse button: {button}")
    _mouse_event(down_flag)
    time.sleep(0.04)
    _mouse_event(up_flag)


def scroll_wheel(direction):
    amount = -WHEEL_DELTA if str(direction).lower() == "down" else WHEEL_DELTA
    _mouse_event(MOUSEEVENTF_WHEEL, ctypes.c_ulong(amount).value)


def tap_mouse_combo(keybind):
    normalized = str(keybind).strip().lower()
    match = re.fullmatch(r"(?:(.+)\+)?(left|right) mouse", normalized)
    if not match:
        raise ValueError(f"Unsupported mouse combo: {keybind}")

    modifier, button = match.groups()
    pressed = press_keybind(modifier) if modifier else []
    try:
        click_mouse(button)
    finally:
        if pressed:
            release_keybind(pressed)
