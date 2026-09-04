"""Parsing and editing helpers for configurable keybind modifiers."""

MODIFIER_NAMES = {
    "ctrl", "control", "left ctrl", "right ctrl", "left control", "right control",
    "alt", "left alt", "right alt", "shift", "left shift", "right shift",
}

_MODIFIER_ALIASES = {
    "ctrl": ("ctrl", "Standard"), "control": ("ctrl", "Standard"),
    "left ctrl": ("ctrl", "Left"), "left control": ("ctrl", "Left"),
    "right ctrl": ("ctrl", "Right"), "right control": ("ctrl", "Right"),
    "alt": ("alt", "Standard"), "left alt": ("alt", "Left"), "right alt": ("alt", "Right"),
    "shift": ("shift", "Standard"), "left shift": ("shift", "Left"), "right shift": ("shift", "Right"),
}


def modifier_state(keybind: str) -> tuple[bool, bool, bool, str]:
    """Return Ctrl, Alt, Shift, and preferred side from a keybind string."""
    enabled = {"ctrl": False, "alt": False, "shift": False}
    sides = []
    for part in str(keybind or "").lower().split("+"):
        match = _MODIFIER_ALIASES.get(part.strip())
        if match:
            name, side = match
            enabled[name] = True
            sides.append(side)
    side = next((item for item in sides if item != "Standard"), "Standard")
    return enabled["ctrl"], enabled["alt"], enabled["shift"], side


def apply_modifiers(keybind: str, ctrl: bool, alt: bool, shift: bool, side: str) -> str:
    """Replace modifiers while preserving the primary key(s) in a keybind."""
    keys = [
        part.strip().lower()
        for part in str(keybind or "").split("+")
        if part.strip() and part.strip().lower() not in MODIFIER_NAMES
    ]
    prefix = {"Left": "left ", "Right": "right "}.get(side, "")
    modifiers = []
    if ctrl:
        modifiers.append(f"{prefix}ctrl".strip())
    if alt:
        modifiers.append(f"{prefix}alt".strip())
    if shift:
        modifiers.append(f"{prefix}shift".strip())
    return "+".join(modifiers + keys)
