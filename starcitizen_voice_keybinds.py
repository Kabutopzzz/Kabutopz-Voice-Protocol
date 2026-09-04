"""
Kabutopz Voice Protocol v1.0

Star Citizen voice-command/keybind utility.
Includes Voice Protocol, customization, grouped phrases, editable keybinds,
mining tools, ship finder, radio, guides, and announcements.
"""

import json
import collections
import math
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from pathlib import Path

import sounddevice as sd
import speech_recognition as sr

from win_input import (
    GlobalHotkey,
    hold_keybind,
    parse_global_hotkey,
    scroll_wheel,
    tap_keybind,
    tap_mouse_combo,
)


APP_DIR = Path.home() / ".star_citizen_voice_keybinds"
SETTINGS_FILE = APP_DIR / "settings.json"
COOLDOWN_SECONDS = 1.5
APP_VERSION = "1.0"
COMMAND_SAMPLE_RATE = 16000
COMMAND_VOICE_THRESHOLD = 450
COMMAND_END_SILENCE_SECONDS = 0.45
COMMAND_MAX_CAPTURE_SECONDS = 2.6
COMMAND_PREROLL_CHUNKS = 8

# ---------------------------------------------------------------------------
# ACTIONS
# One canonical row per action/keybind. All alternate spoken phrases live
# separately in DEFAULT_PHRASES and are editable from the PHRASES page.
# ---------------------------------------------------------------------------
ACTIONS = {
    # Ship
    "ship_power_on":       {"label": "Ship Power On",       "category": "Ship Power",          "type": "tap",  "key": "u",             "hold": None},
    "ship_power_off":      {"label": "Ship Power Off",      "category": "Ship Power",          "type": "tap",  "key": "u",             "hold": None},

    # I is reserved for engine/thruster voice actions, per user request.
    "engines_on":          {"label": "Engines / Thrusters On",  "category": "Engines & Lights", "type": "tap", "key": "i", "hold": None},
    "engines_off":         {"label": "Engines / Thrusters Off", "category": "Engines & Lights", "type": "tap", "key": "i", "hold": None},

    "lights_on":           {"label": "Lights On",            "category": "Engines & Lights",    "type": "tap",  "key": "l",             "hold": None},
    "lights_off":          {"label": "Lights Off",           "category": "Engines & Lights",    "type": "tap",  "key": "l",             "hold": None},

    "gear_toggle":         {"label": "Landing Gear Toggle",  "category": "Landing & ATC",       "type": "tap",  "key": "n",             "hold": None},
    "contact_atc":         {"label": "Contact ATC",          "category": "Landing & ATC",       "type": "tap",  "key": "left alt+n",    "hold": None},

    "quantum_toggle":      {"label": "Toggle Quantum / NAV", "category": "Quantum",             "type": "tap",  "key": "b",             "hold": None},
    "quantum_engage":      {"label": "Engage Quantum",       "category": "Quantum",             "type": "hold", "key": "b",             "hold": 1.2},

    "power_shields":       {"label": "Power To Shields",     "category": "Power Management",    "type": "tap",  "key": "o",             "hold": None},
    "power_weapons":       {"label": "Power To Weapons",     "category": "Power Management",    "type": "tap",  "key": "p",             "hold": None},
    # No "power to thrusters" action here because I is now explicitly engine/thruster toggle vocabulary.
    "weapon_power_up":     {"label": "Raise Weapon Power",   "category": "Power Management",    "type": "tap",  "key": "f5",            "hold": None},
    "thruster_power_up":   {"label": "Raise Thruster Power", "category": "Power Management",    "type": "tap",  "key": "f6",            "hold": None},
    "shield_power_up":     {"label": "Raise Shield Power",   "category": "Power Management",    "type": "tap",  "key": "f7",            "hold": None},
    "power_reset":         {"label": "Reset Power",          "category": "Power Management",    "type": "tap",  "key": "f8",            "hold": None},

    "cruise_control":      {"label": "Cruise Control",       "category": "Flight",              "type": "tap",  "key": "c",             "hold": None},
    "flight_mode":         {"label": "Toggle Flight Mode",   "category": "Flight",              "type": "tap",  "key": "left alt+c",    "hold": None},

    "exit_seat":           {"label": "Exit Seat",            "category": "Utility",             "type": "hold", "key": "y",             "hold": 1.2},
    "unlock_components":   {"label": "Unlock Components",    "category": "Utility",             "type": "tap",  "key": "right alt+k",   "hold": None},
    "night_vision":        {"label": "Night Vision",         "category": "Utility",             "type": "tap",  "key": "right alt+l",   "hold": None},

    "mining_mode":         {"label": "Mining Mode",          "category": "Mining & Scanning",   "type": "tap",  "key": "m",             "hold": None},
    "scan_mode":           {"label": "Scan Mode",            "category": "Mining & Scanning",   "type": "tap",  "key": "v",             "hold": None},

    "self_destruct":       {"label": "Self Destruct",        "category": "Special",             "type": "hold", "key": "backspace",     "hold": 1.5},
    "goon_mode":           {"label": "Goon Mode",            "category": "Special",             "type": "hold", "key": "backspace",     "hold": 5.0},
    "quit_star_citizen":    {"label": "Turn Off Star Citizen", "category": "Special",             "type": "tap",  "key": "alt+f4",         "hold": None},

    # Targeting
    # T = select/reset target nearest crosshair; 5 = closest hostile / iterate hostile.
    "target_ship":          {"label": "Target Ship",                "category": "Targeting",        "type": "tap",   "key": "t",       "hold": None},
    "switch_target":        {"label": "Switch Hostile Target",      "category": "Targeting",        "type": "tap",   "key": "5",       "hold": None},

    # Shield face bias
    "shield_front":         {"label": "Raise Front Shields",        "category": "Shields",          "type": "tap",   "key": "num 8",   "hold": None},
    "shield_back":          {"label": "Raise Rear Shields",         "category": "Shields",          "type": "tap",   "key": "num 2",   "hold": None},
    "shield_left":          {"label": "Raise Left Shields",         "category": "Shields",          "type": "tap",   "key": "num 4",   "hold": None},
    "shield_right":         {"label": "Raise Right Shields",        "category": "Shields",          "type": "tap",   "key": "num 6",   "hold": None},
    "shield_top":           {"label": "Raise Top Shields",          "category": "Shields",          "type": "tap",   "key": "num 7",   "hold": None},
    "shield_bottom":        {"label": "Raise Bottom Shields",       "category": "Shields",          "type": "tap",   "key": "num 1",   "hold": None},
    "shield_reset":         {"label": "Reset Shield Levels",        "category": "Shields",          "type": "tap",   "key": "num 5",   "hold": None},

    # Weapon presets/groups. Mouse wheel cycles the currently selected weapon group.
    "weapon_preset_next":   {"label": "Next Weapon Preset",         "category": "Ship Weapons",     "type": "wheel", "key": "down",    "hold": None},
    "weapon_preset_prev":   {"label": "Previous Weapon Preset",     "category": "Ship Weapons",     "type": "wheel", "key": "up",      "hold": None},

    # Interface / MobiGlas
    "hide_chat":            {"label": "Show / Hide Chat",           "category": "Interface",          "type": "tap",         "key": "f12",              "hold": None},
    "mobiglas":             {"label": "Open / Close MobiGlas",      "category": "Interface",          "type": "tap",         "key": "f1",               "hold": None},
    "open_map":             {"label": "Open Starmap",               "category": "Interface",          "type": "tap",         "key": "f2",               "hold": None},
    "ship_zoom":            {"label": "Ship Zoom / Precision Aim",  "category": "Ship Weapons",       "type": "combo_mouse", "key": "left alt+right mouse", "hold": None},

    # On foot
    "open_inventory":        {"label": "Open Inventory",             "category": "On Foot - Utility",   "type": "tap",         "key": "i",                "hold": None},
    "weapon_1":            {"label": "Switch Weapon / Primary",   "category": "On Foot - Weapons",  "type": "tap",  "key": "1",          "hold": None},
    "weapon_2":            {"label": "Secondary Weapon",          "category": "On Foot - Weapons",  "type": "tap",  "key": "2",          "hold": None},
    "weapon_3":            {"label": "Sidearm",                   "category": "On Foot - Weapons",  "type": "tap",  "key": "3",          "hold": None},
    "weapon_4":            {"label": "Weapon Four",               "category": "On Foot - Weapons",  "type": "tap",  "key": "4",          "hold": None},
    "reload":              {"label": "Reload",                    "category": "On Foot - Weapons",  "type": "tap",  "key": "r",          "hold": None},
    "interact":            {"label": "Interact",                  "category": "On Foot - Movement", "type": "tap",  "key": "f",          "hold": None},
    "jump":                {"label": "Jump",                      "category": "On Foot - Movement", "type": "tap",  "key": "space",      "hold": None},
    "crouch":              {"label": "Crouch",                    "category": "On Foot - Movement", "type": "tap",  "key": "c",          "hold": None},
    "sprint":              {"label": "Sprint",                    "category": "On Foot - Movement", "type": "hold", "key": "left shift", "hold": 1.5},
}

DEFAULT_PHRASES = {
    "ship_power_on": [
        "ship power on", "power on", "turn ship on", "turn on ship",
        "start ship", "boot ship"
    ],
    "ship_power_off": [
        "ship power off", "power off", "turn ship off", "turn off ship",
        "shut down ship", "shutdown ship"
    ],

    "engines_on": [
        "engines on", "engine on", "start engines", "start engine",
        "turn engines on", "thrusters on", "thruster on",
        "turn thrusters on", "start thrusters"
    ],
    "engines_off": [
        "engines off", "engine off", "stop engines", "stop engine",
        "turn engines off", "thrusters off", "thruster off",
        "turn thrusters off", "stop thrusters"
    ],

    "lights_on": ["lights on", "turn lights on", "ship lights on"],
    "lights_off": ["lights off", "turn lights off", "ship lights off"],

    "gear_toggle": [
        "landing gear", "gear up", "raise gear", "retract gear", "landing gear up",
        "gear down", "lower gear", "deploy gear", "landing gear down"
    ],
    "contact_atc": [
        "contact atc", "call atc", "request landing",
        "request landing permission", "request takeoff", "request take off"
    ],

    "quantum_toggle": ["toggle quantum", "quantum mode", "nav mode"],
    "quantum_engage": ["engage quantum", "quantum jump", "jump quantum"],

    "power_shields": ["power to shields", "shields power"],
    "power_weapons": ["power to weapons", "weapons power"],
    "weapon_power_up": ["raise weapon power", "increase weapon power"],
    "thruster_power_up": ["raise thruster power", "increase thruster power"],
    "shield_power_up": ["raise shield power", "increase shield power"],
    "power_reset": ["reset power", "balance power"],

    "cruise_control": ["cruise control", "toggle cruise control"],
    "flight_mode": ["toggle flight mode", "decoupled mode", "coupled mode"],

    "exit_seat": ["exit seat", "leave seat", "get out of seat"],
    "unlock_components": ["unlock components"],
    "night_vision": ["night vision", "toggle night vision"],

    "mining_mode": ["mining mode", "start mining"],
    "scan_mode": ["scan mode", "scanner mode"],

    "self_destruct": ["self destruct", "activate self destruct", "start self destruct"],
    "goon_mode": ["goon mode"],
    "quit_star_citizen": ["turn off star citizen"],

    "target_ship": [
        "target ship", "target target", "lock target", "target that ship",
        "select target", "target shit"
    ],
    "switch_target": [
        "switch target", "next target", "cycle target", "change target",
        "next hostile", "switch hostile"
    ],

    "shield_front": [
        "shields front", "shield front", "more shields front",
        "boost front shields", "front shields"
    ],
    "shield_back": [
        "shields back", "shield back", "shields rear", "rear shields",
        "more shields back", "boost rear shields"
    ],
    "shield_left": [
        "shields left", "shield left", "left shields",
        "more shields left", "boost left shields"
    ],
    "shield_right": [
        "shields right", "shield right", "right shields",
        "more shields right", "boost right shields"
    ],
    "shield_top": [
        "shields top", "shield top", "top shields",
        "more shields top", "boost top shields"
    ],
    "shield_bottom": [
        "shields bottom", "shield bottom", "bottom shields",
        "more shields bottom", "boost bottom shields"
    ],
    "shield_reset": [
        "reset shields", "balance shields", "even shields",
        "normalize shields"
    ],

    "weapon_preset_next": [
        "weapon preset", "next weapon preset", "switch weapon preset",
        "next weapon group", "switch weapon group"
    ],
    "weapon_preset_prev": [
        "previous weapon preset", "last weapon preset",
        "previous weapon group", "last weapon group"
    ],

    "open_inventory":        {"label": "Open Inventory",             "category": "On Foot - Utility",   "type": "tap",         "key": "i",                "hold": None},
    "hide_chat": [
        "hide chat", "show chat", "toggle chat", "close chat"
    ],
    "mobiglas": [
        "open mobiglass", "close mobiglass", "toggle mobiglass",
        "open mobi glass", "close mobi glass"
    ],
    "open_map": [
        "open map", "open starmap", "star map", "show map"
    ],
    "ship_zoom": [
        "ship zoom", "zoom ship", "precision targeting",
        "precision aim", "zoom target"
    ],
    "open_inventory": [
        "open inventory", "inventory", "show inventory", "close inventory"
    ],

    "weapon_1": ["switch weapon", "weapon one", "primary weapon", "primary"],
    "weapon_2": ["weapon two", "secondary weapon", "secondary"],
    "weapon_3": ["weapon three", "sidearm", "pistol"],
    "weapon_4": ["weapon four"],
    "reload": ["reload", "reload weapon"],
    "interact": ["interact", "use"],
    "jump": ["jump"],
    "crouch": ["crouch"],
    "sprint": ["sprint", "run"],
}

VOICE_OFF_PHRASES = {
    "computer turn off",
    "computer off",
    "computer stop listening",
    "computer stop",
    "computer disable",
}

# ---------------------------------------------------------------------------
# Mining signature table from the user-provided reference image.
# Values are the "Primary" / 1x RS signature. Multiples are computed 1-10x.
# ---------------------------------------------------------------------------
MINING_PRIMARY = {
    "ice": 4300,
    "aluminium": 4285,
    "aluminum": 4285,  # US spelling alias
    "iron": 4270,
    "silicon": 4255,
    "copper": 4240,
    "corundum": 4225,
    "quartz": 4210,
    "tin": 4195,
    "hephaestanite": 4180,
    "torite": 3900,
    "agricium": 3885,
    "tungsten": 3870,
    "titanium": 3855,
    "aslarite": 3840,
    "laranite": 3825,
    "bexalite": 3600,
    "gold": 3585,
    "borase": 3570,
    "taranite": 3555,
    "beryl": 3540,
    "lindinium": 3400,
    "riccite": 3385,
    "ouratite": 3370,
    "savrililum": 3200,
    "stileron": 3185,
    "quantainium": 3170,
}

MINING_DISPLAY_ORDER = [
    "ice", "aluminium", "iron", "silicon", "copper", "corundum", "quartz",
    "tin", "hephaestanite", "torite", "agricium", "tungsten", "titanium",
    "aslarite", "laranite", "bexalite", "gold", "borase", "taranite", "beryl",
    "lindinium", "riccite", "ouratite", "savrililum", "stileron", "quantainium"
]


# ---------------------------------------------------------------------------
# Spoken Star Citizen keybind reference.
# This is intentionally a useful default-reference set, not a claim that
# every possible Star Citizen bind is represented.
# ---------------------------------------------------------------------------
KEYBIND_REFERENCE = {
    "w": ["Move forward / ship throttle up"],
    "a": ["Move or strafe left"],
    "s": ["Move backward / ship throttle down"],
    "d": ["Move or strafe right"],
    "q": ["Lean left on foot / roll left in ship"],
    "e": ["Lean right on foot / roll right in ship"],
    "r": ["Reload on foot", "Flight Ready in ship", "Iterate target subsystem in newer targeting controls"],
    "t": ["Suit light on foot", "Select target nearest the crosshair in ship"],
    "u": ["Ship power toggle"],
    "i": ["Open inventory on foot in this voice profile", "Engines / thrusters toggle in this voice profile"],
    "f": ["Interact"],
    "g": ["Grenade on foot", "Cycle gimbal mode in ship"],
    "h": ["Hold to deploy decoy"],
    "j": ["Deploy noise countermeasure"],
    "c": ["Cruise control in ship", "Crouch phrase in this voice profile if customized that way"],
    "x": ["Prone on foot / space brake in ship"],
    "y": ["Hold to exit seat"],
    "b": ["Quantum / NAV mode; hold for quantum travel in this profile"],
    "n": ["Landing gear / landing mode"],
    "1": ["Sidearm in current default references; this voice profile may use it for Switch Weapon / Primary"],
    "2": ["Primary weapon in current default references"],
    "3": ["Secondary weapon in current default references"],
    "4": ["Target closest ship targeting you in newer targeting controls"],
    "5": ["Target closest hostile ship in newer targeting controls"],
    "6": ["Target closest friendly ship in newer targeting controls"],
    "7": ["Target closest contact in newer targeting controls"],
    "space": ["Jump"],
    "left shift": ["Sprint on foot / boost in ship"],
    "left control": ["Crouch on foot / hold for auto land in ship"],
    "f1": ["Open or close MobiGlas"],
    "f2": ["Open Starmap"],
    "f4": ["Cycle camera view"],
    "f11": ["Open Contacts"],
    "f12": ["Show or hide chat"],
    "numpad 8": ["Raise front shield level"],
    "numpad 2": ["Raise rear shield level"],
    "numpad 4": ["Raise left shield level"],
    "numpad 6": ["Raise right shield level"],
    "numpad 7": ["Raise top shield level"],
    "numpad 1": ["Raise bottom shield level"],
    "numpad 5": ["Reset shield levels"],
    "right alt+k": ["Unlock ship component ports"],
    "left alt+n": ["Request landing / takeoff"],
    "left alt+c": ["Toggle coupled / decoupled flight mode"],
    "left alt+right mouse": ["Precision targeting / ship target zoom"],
}


SHIP_API_BASE = "https://api.star-citizen.wiki/api"
GUIDES_URL = "https://www.youtube.com/watch?v=9HFhtRZU03Q&list=PLfLI1pCiRQOsMD5FwlHjlIzBdPLzE-ABo&pp=0gcJCf8COCosWNinsAgC"
ANNOUNCEMENTS_URL = "https://robertsspaceindustries.com/spectrum/community/SC/forum/1"
BUY_ME_A_COFFEE_URL = "https://buymeacoffee.com/kabutopz"

# Fallback hotspot snapshot used only if the live community API request fails.
# Iron values are current 4.10-era hotspot data from the supplied/reference research.
MINING_LOCATION_FALLBACK = {
    "iron": [
        "Pyro V-c (Adir)",
        "Pyro V-b (Vatra)",
        "Pyro III (Bloom)",
        "Magda",
        "Lyria",
        "Calliope",
        "Pyro I",
        "Pyro II (Monox)",
        "microTech",
        "Pyro V-e (Fuego)",
        "Pyro V-f (Vuur)",
        "Pyro V-d (Fairo)",
        "Pyro IV",
        "Wala",
        "Glaciem Ring",
        "Yela Asteroid Belt",
        "Akiro Cluster",
        "Aaron Halo",
    ]
}

THEME_PRESETS = {
    "Midnight Blue": {
        "bg": "#0b0f14", "panel": "#111821", "panel2": "#151f2b",
        "border": "#263341", "text": "#edf3f8", "muted": "#8493a3",
        "accent": "#4da3ff",
    },
    "Blackout": {
        "bg": "#050505", "panel": "#0d0d0d", "panel2": "#151515",
        "border": "#303030", "text": "#f4f4f4", "muted": "#8e8e8e",
        "accent": "#ffffff",
    },
    "Purple Nebula": {
        "bg": "#0d0913", "panel": "#171021", "panel2": "#21172f",
        "border": "#3a2851", "text": "#f4edff", "muted": "#9d8caf",
        "accent": "#a970ff",
    },
    "Cyan": {
        "bg": "#061014", "panel": "#0b1b22", "panel2": "#102831",
        "border": "#204452", "text": "#ebfbff", "muted": "#82a7b0",
        "accent": "#34d7ff",
    },
    "Industrial Orange": {
        "bg": "#120d08", "panel": "#1c150e", "panel2": "#291e13",
        "border": "#4b3824", "text": "#fff4e8", "muted": "#ad9984",
        "accent": "#ffad42",
    },
    "Danger Red": {
        "bg": "#110809", "panel": "#1d0f11", "panel2": "#2a1518",
        "border": "#512b30", "text": "#fff1f2", "muted": "#b08d91",
        "accent": "#ff5d6c",
    },
}
LEGACY_DEFAULT_THEME = THEME_PRESETS["Midnight Blue"].copy()
DEFAULT_THEME = THEME_PRESETS["Industrial Orange"].copy()



def resource_path(relative_path):
    """Return a path that works both from source and from a PyInstaller EXE."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


class VoiceKeybindApp(tk.Tk):
    RED = "#ff5d6c"

    def __init__(self):
        super().__init__()

        self.title(f"Kabutopz Voice Protocol v{APP_VERSION}")

        # Kabutopz app/taskbar/window icon.
        try:
            from PIL import Image, ImageTk
            icon_path = resource_path("assets/kabutopz_app_icon.png")
            icon_image = Image.open(icon_path).convert("RGBA")
            self.app_icon_photo = ImageTk.PhotoImage(icon_image)
            self.iconphoto(True, self.app_icon_photo)
        except Exception:
            pass
        self.geometry("1240x820")
        self.minsize(1020, 700)

        self.running = False
        self.worker = None
        self.events = queue.Queue()
        self.last_triggered = {}
        self.recognizer = sr.Recognizer()
        self.audio_devices = []
        self.selected_device = "__default__"
        self.tts_process = None
        self.tts_lock = threading.Lock()
        self.voice_toggle_hotkey = None
        self.installed_voices = []
        self.history_watermark_photo = None
        self.header_logo_photo = None
        self.header_love_photo = None
        self.support_button_photo = None
        self.app_icon_photo = None
        self.history_watermark_source = None

        self.settings = self._load_settings()
        self.theme = self._load_theme()
        self._load_watermark_source()
        self.custom_actions = self.settings.get("custom_actions", [])
        self._load_custom_actions_into_registry()
        self.phrases = self._load_phrases()
        self.keybinds = self._load_keybinds()

        self.tracked = {
            "bg": [], "panel": [], "panel2": [], "text": [],
            "muted": [], "border": [], "accent": []
        }
        self.button_theme_roles = {}
        self.toggle_theme_roles = {}

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_shell()
        self._build_voice_page()
        self._build_customize_page()
        self._build_phrases_page()
        self._build_custom_words_page()
        self._build_keybinds_page()
        self._build_mining_page()
        self._build_ship_finder_page()
        self._build_guides_page()
        self._build_announcements_page()

        self._configure_voice_toggle_hotkey(
            self.settings.get("voice_toggle_hotkey", ""),
            show_error=False,
        )
        self.refresh_devices()
        self._refresh_tts_voices()
        self.apply_theme()
        self.show_page("VOICE PROTOCOL")
        self.after(50, self._drain_events)

    # -------------------- settings --------------------
    def _load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {
            "theme": DEFAULT_THEME.copy(),
            "voice_feedback": True,
            "tts_volume": 80,
            "tts_voice": "",
            "voice_toggle_hotkey": "",
            "keybinds": {},
            "custom_actions": [],
            "phrases": DEFAULT_PHRASES.copy(),
        }

    def _load_theme(self):
        """Load a complete theme without overwriting a user's custom colors."""
        saved = self.settings.get("theme")
        if saved == LEGACY_DEFAULT_THEME:
            # Existing installs that never changed the old default should
            # follow the new Industrial Orange default automatically.
            return DEFAULT_THEME.copy()
        if not isinstance(saved, dict):
            return DEFAULT_THEME.copy()
        return {
            key: str(saved.get(key, DEFAULT_THEME[key]))
            for key in DEFAULT_THEME
        }

    def _matching_theme_preset(self):
        """Return the preset name for the active colors, if one matches."""
        for name, preset in THEME_PRESETS.items():
            if self.theme == preset:
                return name
        return None

    def _load_custom_actions_into_registry(self):
        """Merge saved CUSTOM WORDS commands into the runtime registry."""
        for item in self.custom_actions:
            if not isinstance(item, dict):
                continue
            action_id = str(item.get("id", "")).strip()
            label = str(item.get("label", "")).strip()
            category = str(item.get("category", "Custom")).strip() or "Custom"
            key = str(item.get("key", "")).strip().lower()
            action_type = str(item.get("type", "tap")).strip().lower()
            hold = item.get("hold")

            if not action_id or not label or not key:
                continue
            if action_type not in {"tap", "hold", "wheel", "combo_mouse"}:
                action_type = "tap"

            ACTIONS[action_id] = {
                "label": label,
                "category": category,
                "type": action_type,
                "key": key,
                "hold": hold,
                "custom": True,
            }

            phrases = item.get("phrases", [])
            if isinstance(phrases, list):
                DEFAULT_PHRASES[action_id] = [
                    str(p).strip().lower()
                    for p in phrases
                    if str(p).strip()
                ]

    def _load_phrases(self):
        saved = self.settings.get("phrases", {})
        merged = {}
        for action_id in ACTIONS:
            vals = saved.get(action_id, DEFAULT_PHRASES.get(action_id, []))
            if not isinstance(vals, list):
                vals = DEFAULT_PHRASES.get(action_id, [])
            merged[action_id] = [str(x).strip().lower() for x in vals if str(x).strip()]
        return merged

    def _load_keybinds(self):
        saved = self.settings.get("keybinds", {})
        result = {}
        for action_id, action in ACTIONS.items():
            value = str(saved.get(action_id, action["key"])).strip().lower()
            result[action_id] = value or action["key"]
        return result

    def _save_settings(self):
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            self.settings["theme"] = self.theme
            self.settings["voice_feedback"] = bool(self.voice_feedback_var.get())
            self.settings["tts_volume"] = int(self.tts_volume_var.get())
            self.settings["tts_voice"] = self.tts_voice_var.get()
            if hasattr(self, "voice_toggle_hotkey_var"):
                self.settings["voice_toggle_hotkey"] = (
                    self.voice_toggle_hotkey_var.get().strip().lower()
                )
            self.settings["phrases"] = self.phrases
            self.settings["keybinds"] = self.keybinds
            self.settings["custom_actions"] = self.custom_actions
            SETTINGS_FILE.write_text(
                json.dumps(self.settings, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    # -------------------- Kabutopz watermark --------------------
    def _load_watermark_source(self):
        try:
            from PIL import Image
            path = resource_path("assets/kabutopz_watermark.jpg")
            self.history_watermark_source = Image.open(path).convert("RGBA")
        except Exception:
            self.history_watermark_source = None

    def _refresh_history_watermark(self, *_):
        """Render a faint fixed Kabutopz mark across the Command History area."""
        if not hasattr(self, "history_watermark") or self.history_watermark_source is None:
            return

        try:
            from PIL import Image, ImageTk, ImageColor

            w = max(320, self.history_watermark.winfo_width())
            h = max(240, self.history_watermark.winfo_height())

            src = self.history_watermark_source.copy()
            # Fit the logo into roughly 62% of the history panel.
            max_w = int(w * 0.62)
            max_h = int(h * 0.62)
            src.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

            # Remove the original white field by blending it heavily into the
            # current history background. This keeps the branding visible
            # without making command text hard to read.
            bg_rgb = ImageColor.getrgb(self.theme["panel2"])
            canvas = Image.new("RGBA", (w, h), bg_rgb + (255,))

            # Convert near-white pixels to transparent, then make the artwork faint.
            pixels = src.load()
            for y in range(src.height):
                for x in range(src.width):
                    r, g, b, a = pixels[x, y]
                    if r > 242 and g > 242 and b > 242:
                        pixels[x, y] = (r, g, b, 0)
                    else:
                        pixels[x, y] = (r, g, b, 42)

            x = (w - src.width) // 2
            y = (h - src.height) // 2
            canvas.alpha_composite(src, (x, y))

            self.history_watermark_photo = ImageTk.PhotoImage(canvas)
            self.history_watermark.configure(image=self.history_watermark_photo)
        except Exception:
            pass

    # -------------------- theme helpers --------------------
    def _track(self, widget, *kinds):
        for kind in kinds:
            self.tracked[kind].append(widget)
        return widget

    def _walk_widgets(self, parent=None):
        """Yield every existing UI widget so theme changes are comprehensive."""
        parent = self if parent is None else parent
        for child in parent.winfo_children():
            yield child
            yield from self._walk_widgets(child)

    @staticmethod
    def _accent_text_color(color):
        """Choose readable text for an accent-colored button."""
        try:
            color = color.lstrip("#")
            red, green, blue = (
                int(color[0:2], 16),
                int(color[2:4], 16),
                int(color[4:6], 16),
            )
            brightness = (red * 299 + green * 587 + blue * 114) / 1000
            return "#130d08" if brightness >= 145 else "#ffffff"
        except Exception:
            return "#130d08"

    def _remember_widget_theme_roles(self):
        """Assign durable roles before colors are changed by a new preset."""
        for widget in self._walk_widgets():
            if isinstance(widget, tk.Button) and widget not in self.button_theme_roles:
                try:
                    background = widget.cget("bg").lower()
                    self.button_theme_roles[widget] = (
                        "accent"
                        if background == self.theme["accent"].lower()
                        else "secondary"
                    )
                except Exception:
                    self.button_theme_roles[widget] = "secondary"

            if (
                isinstance(widget, (tk.Checkbutton, tk.Radiobutton))
                and widget not in self.toggle_theme_roles
            ):
                try:
                    parent_background = widget.master.cget("bg").lower()
                    self.toggle_theme_roles[widget] = (
                        "panel2"
                        if parent_background == self.theme["panel2"].lower()
                        else "panel"
                    )
                except Exception:
                    self.toggle_theme_roles[widget] = "panel"

    def _apply_standard_widget_theme(self, t):
        """Theme controls that do not accept the generic tracked-widget API."""
        self._remember_widget_theme_roles()
        accent_text = self._accent_text_color(t["accent"])

        for widget, role in list(self.button_theme_roles.items()):
            try:
                if not widget.winfo_exists():
                    del self.button_theme_roles[widget]
                    continue
                if role == "accent":
                    widget.configure(
                        bg=t["accent"], fg=accent_text,
                        activebackground=t["accent"],
                        activeforeground=accent_text,
                    )
                else:
                    widget.configure(
                        bg=t["panel2"], fg=t["text"],
                        activebackground=t["border"],
                        activeforeground=t["text"],
                    )
            except Exception:
                pass

        for widget, role in list(self.toggle_theme_roles.items()):
            try:
                if not widget.winfo_exists():
                    del self.toggle_theme_roles[widget]
                    continue
                background = t[role]
                widget.configure(
                    bg=background, fg=t["text"], selectcolor=t["panel2"],
                    activebackground=background, activeforeground=t["text"],
                )
            except Exception:
                pass

        for widget in self._walk_widgets():
            try:
                if isinstance(widget, tk.Entry):
                    widget.configure(
                        bg=t["panel2"], fg=t["text"],
                        insertbackground=t["text"],
                        selectbackground=t["border"],
                        selectforeground=t["text"],
                    )
                elif isinstance(widget, (tk.Text, tk.Listbox)):
                    widget.configure(
                        bg=t["panel2"], fg=t["text"],
                        insertbackground=t["text"],
                        selectbackground=t["border"],
                        selectforeground=t["text"],
                    )
                elif isinstance(widget, tk.Canvas):
                    widget.configure(bg=t["panel2"])
                elif isinstance(widget, tk.Scale):
                    widget.configure(
                        bg=t["panel"], fg=t["text"],
                        troughcolor=t["panel2"], activebackground=t["accent"],
                    )
            except Exception:
                pass

    def apply_theme(self):
        t = self.theme
        self.configure(bg=t["bg"])

        for w in self.tracked["bg"]:
            try: w.configure(bg=t["bg"])
            except Exception: pass
        for w in self.tracked["panel"]:
            try: w.configure(bg=t["panel"])
            except Exception: pass
        for w in self.tracked["panel2"]:
            try: w.configure(bg=t["panel2"])
            except Exception: pass
        for w in self.tracked["text"]:
            try: w.configure(fg=t["text"])
            except Exception: pass
        for w in self.tracked["muted"]:
            try: w.configure(fg=t["muted"])
            except Exception: pass
        for w in self.tracked["border"]:
            try: w.configure(highlightbackground=t["border"])
            except Exception: pass
        for w in self.tracked["accent"]:
            try: w.configure(fg=t["accent"])
            except Exception: pass

        self.style.configure(
            "Dark.TCombobox",
            fieldbackground=t["panel2"], background=t["panel2"],
            foreground=t["text"], arrowcolor=t["text"],
            bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
            padding=8,
        )
        self.style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", t["panel2"])],
            foreground=[("readonly", t["text"])],
            selectbackground=[("readonly", t["panel2"])],
            selectforeground=[("readonly", t["text"])],
        )
        self.style.configure(
            "Vertical.TScrollbar",
            background=t["panel2"], troughcolor=t["panel"],
            bordercolor=t["border"], arrowcolor=t["text"],
        )

        self._apply_standard_widget_theme(t)

        for name in ("history", "command_list", "phrase_text", "phrase_preview", "keybind_search_list", "keybind_phrase_preview", "custom_existing_list", "custom_existing_phrase_list", "mining_table", "ship_results"):
            if hasattr(self, name):
                widget = getattr(self, name)
                try:
                    widget.configure(
                        bg=t["panel2"], fg=t["text"],
                        insertbackground=t["text"],
                        selectbackground=t["border"],
                        selectforeground=t["text"],
                    )
                except Exception:
                    pass

        if hasattr(self, "listen_button"):
            if self.running:
                self.listen_button.configure(
                    bg=self.RED,
                    fg="#ffffff",
                    activebackground=self.RED,
                    activeforeground="#ffffff",
                )
            else:
                accent_text = self._accent_text_color(t["accent"])
                self.listen_button.configure(
                    bg=t["accent"], activebackground=t["accent"],
                    fg=accent_text, activeforeground=accent_text,
                )

        if hasattr(self, "history_watermark"):
            self.after(20, self._refresh_history_watermark)
        self._save_settings()

    def _choose_color(self, key, label):
        chosen = colorchooser.askcolor(
            color=self.theme[key],
            title=f"Choose {label} Color"
        )[1]
        if chosen:
            self.theme[key] = chosen
            self.theme_preset_var.set("Custom")
            self.apply_theme()

    def _preset_changed(self, *_):
        name = self.theme_preset_var.get()
        if name in THEME_PRESETS:
            self.theme = THEME_PRESETS[name].copy()
            self.apply_theme()

    def _reset_theme(self):
        self.theme = DEFAULT_THEME.copy()
        self.theme_preset_var.set("Industrial Orange")
        self.apply_theme()

    # -------------------- shell --------------------
    def _build_shell(self):
        t = self.theme

        top = self._track(tk.Frame(self, bg=t["bg"]), "bg")
        top.pack(fill="x", padx=28, pady=(22, 10))

        left = self._track(tk.Frame(top, bg=t["bg"]), "bg")
        left.pack(side="left")

        brand_row = self._track(tk.Frame(left, bg=t["bg"]), "bg")
        brand_row.pack(anchor="w")

        # Salute Kabutopz mascot on the far left.
        try:
            from PIL import Image, ImageTk
            logo_path = resource_path("assets/kabutopz_header_full.png")
            logo_image = Image.open(logo_path).convert("RGBA")
            logo_image.thumbnail((112, 88), Image.Resampling.LANCZOS)
            self.header_logo_photo = ImageTk.PhotoImage(logo_image)

            logo_label = tk.Label(
                brand_row,
                image=self.header_logo_photo,
                bg=t["bg"],
                bd=0,
                highlightthickness=0,
            )
            self._track(logo_label, "bg")
            logo_label.pack(side="left", padx=(0, 16))
        except Exception:
            pass

        title_block = self._track(tk.Frame(brand_row, bg=t["bg"]), "bg")
        title_block.pack(side="left", anchor="center")

        title = tk.Label(
            title_block,
            text="KABUTOPZ VOICE PROTOCOL",
            font=("Segoe UI", 22, "bold"),
            fg=t["text"],
            bg=t["bg"]
        )
        self._track(title, "bg", "text")
        title.pack(anchor="w")

        subtitle = tk.Label(
            title_block,
            text=f"VERSION {APP_VERSION} • POWERED BY CHAT",
            font=("Segoe UI", 11, "bold"),
            fg=t["accent"],
            bg=t["bg"]
        )
        self._track(subtitle, "bg", "accent")
        subtitle.pack(anchor="w")

        # Love Kabutops graphic beside the title.
        try:
            from PIL import Image, ImageTk
            love_path = resource_path("assets/kabutopz_love.png")
            love_image = Image.open(love_path).convert("RGBA")
            love_image.thumbnail((116, 96), Image.Resampling.LANCZOS)
            self.header_love_photo = ImageTk.PhotoImage(love_image)

            love_label = tk.Label(
                brand_row,
                image=self.header_love_photo,
                bg=t["bg"],
                bd=0,
                highlightthickness=0,
            )
            self._track(love_label, "bg")
            love_label.pack(side="left", padx=(22, 0))
        except Exception:
            pass

        nav = self._track(tk.Frame(top, bg=t["bg"]), "bg")
        nav.pack(side="right")

        # Buy Me a Coffee link, immediately left of the page selector.
        support = self._track(
            tk.Frame(
                top,
                bg=t["panel"],
                highlightbackground=t["border"],
                highlightthickness=1,
                cursor="hand2",
            ),
            "panel",
            "border",
        )
        support.pack(side="right", padx=(0, 18), anchor="center")
        support.bind("<Button-1>", self._open_buy_me_a_coffee)

        support_title = tk.Label(
            support,
            text="Support is appreciated!",
            font=("Segoe UI", 9, "bold"),
            fg=t["text"],
            bg=t["panel"],
            cursor="hand2",
        )
        self._track(support_title, "panel", "text")
        support_title.pack(padx=10, pady=(6, 2))
        support_title.bind("<Button-1>", self._open_buy_me_a_coffee)

        try:
            from PIL import Image, ImageTk

            button_path = resource_path("assets/buy_me_a_coffee.png")
            button_image = Image.open(button_path).convert("RGBA")
            button_image.thumbnail((190, 56), Image.Resampling.LANCZOS)
            self.support_button_photo = ImageTk.PhotoImage(button_image)

            support_button = tk.Label(
                support,
                image=self.support_button_photo,
                bg=t["panel"],
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )
            self._track(support_button, "panel")
            support_button.pack(padx=8, pady=(0, 7))
            support_button.bind("<Button-1>", self._open_buy_me_a_coffee)
        except Exception:
            fallback = tk.Label(
                support,
                text="BUY ME A COFFEE",
                font=("Segoe UI", 9, "bold"),
                fg="#111111",
                bg="#ffdd00",
                padx=18,
                pady=8,
                cursor="hand2",
            )
            fallback.pack(padx=10, pady=(0, 8))
            fallback.bind("<Button-1>", self._open_buy_me_a_coffee)

        page_label = tk.Label(
            nav, text="PAGE",
            font=("Segoe UI", 8, "bold"),
            fg=t["muted"], bg=t["bg"]
        )
        self._track(page_label, "bg", "muted").pack(anchor="e", pady=(0, 5))

        self.page_var = tk.StringVar(value="VOICE PROTOCOL")
        self.page_combo = ttk.Combobox(
            nav,
            textvariable=self.page_var,
            values=["VOICE PROTOCOL", "CUSTOMIZE", "PHRASES", "CUSTOM WORDS", "KEYBINDS", "MINING MODE", "SHIP FINDER", "GUIDES", "ANNOUNCEMENTS"],
            state="readonly",
            style="Dark.TCombobox",
            width=24,
        )
        self.page_combo.pack()
        self.page_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.show_page(self.page_var.get())
        )

        self.page_host = self._track(tk.Frame(self, bg=t["bg"]), "bg")
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(4, 24))

    def _open_buy_me_a_coffee(self, *_):
        webbrowser.open_new_tab(BUY_ME_A_COFFEE_URL)

    def show_page(self, name):
        for page in (
            self.voice_page,
            self.customize_page,
            self.phrases_page,
            self.custom_words_page,
            self.keybinds_page,
            self.mining_page,
            self.ship_finder_page,
            self.guides_page,
            self.announcements_page,
        ):
            page.pack_forget()

        pages = {
            "CUSTOMIZE": self.customize_page,
            "PHRASES": self.phrases_page,
            "CUSTOM WORDS": self.custom_words_page,
            "KEYBINDS": self.keybinds_page,
            "MINING MODE": self.mining_page,
            "SHIP FINDER": self.ship_finder_page,
            "GUIDES": self.guides_page,
            "ANNOUNCEMENTS": self.announcements_page,
        }
        pages.get(name, self.voice_page).pack(fill="both", expand=True)


    def _panel(self, parent):
        t = self.theme
        p = tk.Frame(
            parent, bg=t["panel"],
            highlightthickness=1,
            highlightbackground=t["border"]
        )
        self._track(p, "panel", "border")
        return p

    def _label(self, parent, text, font=("Segoe UI", 9), muted=False, panel2=False):
        t = self.theme
        bg_key = "panel2" if panel2 else "panel"
        l = tk.Label(
            parent, text=text, font=font,
            fg=t["muted"] if muted else t["text"],
            bg=t[bg_key]
        )
        self._track(l, bg_key, "muted" if muted else "text")
        return l

    # -------------------- Voice Protocol page --------------------
    def _build_voice_page(self):
        t = self.theme
        self.voice_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        left = self._panel(self.voice_page)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        head = self._track(tk.Frame(left, bg=t["panel"]), "panel")
        head.pack(fill="x", padx=18, pady=(16, 10))
        self._label(
            head, "COMMAND HISTORY", ("Segoe UI", 10, "bold")
        ).pack(side="left")
        self.command_count = self._label(
            head, "0 events", ("Segoe UI", 8), muted=True
        )
        self.command_count.pack(side="right")

        hist_frame = self._track(tk.Frame(left, bg=t["panel2"]), "panel2")
        hist_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Permanent Kabutopz branding layer for the Command History section.
        self.history_watermark = tk.Label(
            hist_frame,
            bg=t["panel2"],
            bd=0,
            highlightthickness=0,
        )
        self._track(self.history_watermark, "panel2")
        self.history_watermark.place(x=0, y=0, relwidth=1, relheight=1)
        self.history_watermark.bind("<Configure>", self._refresh_history_watermark)

        history_inner = self._track(
            tk.Frame(hist_frame, bg=t["panel2"]),
            "panel2"
        )
        # Small border around the log leaves the branded background visibly
        # integrated with Command History instead of placing a separate logo.
        history_inner.pack(fill="both", expand=True, padx=9, pady=9)

        self.history = tk.Text(
            history_inner,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", borderwidth=0,
            font=("Cascadia Mono", 9),
            wrap="word", padx=14, pady=12,
            state="disabled",
        )
        self.history.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(history_inner, command=self.history.yview)
        sb.pack(side="right", fill="y")
        self.history.configure(yscrollcommand=sb.set)

        # A second faint mark is embedded in the log itself so it remains part
        # of Command History even when the window is resized.
        self.after(150, self._refresh_history_watermark)

        right = self._track(
            tk.Frame(self.voice_page, bg=t["bg"], width=390), "bg"
        )
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        control = self._panel(right)
        control.pack(fill="x", pady=(0, 10))

        self._label(
            control, "VOICE PROTOCOL", ("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=18, pady=(16, 10))

        self.status_label = self._label(
            control, "OFFLINE", ("Segoe UI", 9, "bold")
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 8))

        self.listen_button = tk.Button(
            control,
            text="START LISTENING",
            command=self.toggle_listening,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            pady=11,
        )
        self.listen_button.pack(fill="x", padx=18, pady=(0, 12))

        self._label(
            control,
            'Voice off: "computer turn off"',
            ("Segoe UI", 8),
            muted=True,
        ).pack(anchor="w", padx=18, pady=(0, 10))

        self._label(
            control,
            "VOICE ACTIVATION TOGGLE KEYBIND (OPTIONAL)",
            ("Segoe UI", 8, "bold"),
            muted=True,
        ).pack(anchor="w", padx=18, pady=(0, 5))

        self.voice_toggle_hotkey_var = tk.StringVar(
            value=str(self.settings.get("voice_toggle_hotkey", "")).strip()
        )
        hotkey_row = self._track(
            tk.Frame(control, bg=t["panel"]), "panel"
        )
        hotkey_row.pack(fill="x", padx=18, pady=(0, 5))

        self.voice_toggle_hotkey_entry = tk.Entry(
            hotkey_row,
            textvariable=self.voice_toggle_hotkey_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 9),
        )
        self.voice_toggle_hotkey_entry.pack(
            side="left", fill="x", expand=True, ipady=7
        )
        self.voice_toggle_hotkey_entry.bind(
            "<Return>", lambda _: self._save_voice_toggle_hotkey()
        )

        save_hotkey = tk.Button(
            hotkey_row,
            text="SAVE",
            command=self._save_voice_toggle_hotkey,
            bg=t["accent"], fg=self._accent_text_color(t["accent"]),
            activebackground=t["accent"],
            activeforeground=self._accent_text_color(t["accent"]),
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), padx=10, pady=7,
        )
        save_hotkey.pack(side="left", padx=(8, 0))

        clear_hotkey = tk.Button(
            hotkey_row,
            text="CLEAR",
            command=self._clear_voice_toggle_hotkey,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), padx=9, pady=7,
        )
        clear_hotkey.pack(side="left", padx=(6, 0))

        self.voice_toggle_hotkey_status = self._label(
            control,
            "Leave blank to disable the keybind. Example: F8 or Ctrl+Shift+V.",
            ("Segoe UI", 8),
            muted=True,
        )
        self.voice_toggle_hotkey_status.pack(
            anchor="w", padx=18, pady=(0, 10)
        )

        self._label(
            control, "RECORDING DEVICE",
            ("Segoe UI", 8, "bold"),
            muted=True,
        ).pack(anchor="w", padx=18, pady=(0, 6))

        self.device_var = tk.StringVar(
            value="Windows Default Recording Device"
        )
        self.device_combo = ttk.Combobox(
            control,
            textvariable=self.device_var,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.device_combo.pack(fill="x", padx=18, pady=(0, 7))
        self.device_combo.bind(
            "<<ComboboxSelected>>",
            self._device_selected,
        )

        refresh = tk.Button(
            control,
            text="REFRESH MICROPHONES",
            command=self.refresh_devices,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"],
            activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"),
            pady=7,
        )
        self._track(refresh, "panel2", "text")
        refresh.pack(fill="x", padx=18, pady=(0, 10))

        self.voice_feedback_var = tk.BooleanVar(
            value=self.settings.get("voice_feedback", True)
        )
        self.voice_feedback_check = tk.Checkbutton(
            control,
            text='Voice feedback: "Command confirmed."',
            variable=self.voice_feedback_var,
            command=self._save_settings,
            font=("Segoe UI", 8),
        )
        self.voice_feedback_check.pack(
            anchor="w", padx=18, pady=(0, 10)
        )

        self._label(
            control, "TTS VOICE",
            ("Segoe UI", 8, "bold"),
            muted=True,
        ).pack(anchor="w", padx=18, pady=(0, 6))

        self.tts_voice_var = tk.StringVar(
            value=self.settings.get("tts_voice", "")
        )
        self.tts_voice_combo = ttk.Combobox(
            control,
            textvariable=self.tts_voice_var,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.tts_voice_combo.pack(fill="x", padx=18, pady=(0, 8))
        self.tts_voice_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self._save_settings()
        )

        self._label(
            control, "TTS VOLUME",
            ("Segoe UI", 8, "bold"),
            muted=True,
        ).pack(anchor="w", padx=18, pady=(0, 3))

        self.tts_volume_var = tk.IntVar(
            value=int(self.settings.get("tts_volume", 80))
        )
        self.tts_volume_slider = tk.Scale(
            control,
            from_=0, to=100,
            orient="horizontal",
            variable=self.tts_volume_var,
            command=lambda value: self._save_settings(),
            showvalue=True,
            resolution=1,
            bg=t["panel"],
            fg=t["text"],
            troughcolor=t["panel2"],
            highlightthickness=0,
            activebackground=t["accent"],
        )
        self.tts_volume_slider.pack(fill="x", padx=18, pady=(0, 8))

        stop_tts = tk.Button(
            control,
            text="STOP TALKING",
            command=self._stop_tts,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"],
            activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"),
            pady=7,
        )
        self._track(stop_tts, "panel2", "text")
        stop_tts.pack(fill="x", padx=18, pady=(0, 10))

        self.mic_label = self._label(
            control,
            "Microphone: not initialized",
            ("Segoe UI", 8),
            muted=True,
        )
        self.mic_label.pack(anchor="w", padx=18, pady=(0, 14))

        catalog = self._panel(right)
        catalog.pack(fill="both", expand=True)

        self._label(
            catalog, "COMMANDS",
            ("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self.category_var = tk.StringVar(value="Ship Power")
        category_values = []
        for a in ACTIONS.values():
            if a["category"] not in category_values:
                category_values.append(a["category"])

        cat_combo = ttk.Combobox(
            catalog,
            textvariable=self.category_var,
            values=category_values,
            state="readonly",
            style="Dark.TCombobox",
        )
        cat_combo.pack(fill="x", padx=18, pady=(0, 10))
        cat_combo.bind(
            "<<ComboboxSelected>>",
            self._refresh_command_list,
        )

        self.command_list = tk.Listbox(
            catalog,
            bg=t["panel2"], fg=t["text"],
            selectbackground=t["border"],
            selectforeground=t["text"],
            relief="flat", bd=0,
            activestyle="none",
            font=("Segoe UI", 9),
            highlightthickness=0,
        )
        self.command_list.pack(
            fill="both", expand=True,
            padx=14, pady=(0, 14)
        )
        self.command_list.bind(
            "<Double-Button-1>",
            self._test_selected,
        )
        self._refresh_command_list()

    # -------------------- Customize page --------------------
    def _build_customize_page(self):
        t = self.theme
        self.customize_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.customize_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "CUSTOMIZE UI", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            "Theme editing lives here so the Voice Protocol page stays clean.",
            ("Segoe UI", 9),
            muted=True,
        ).pack(anchor="w", pady=(4, 22))

        self._label(
            inner, "THEME PRESET",
            ("Segoe UI", 8, "bold"),
            muted=True,
        ).pack(anchor="w", pady=(0, 6))

        self.theme_preset_var = tk.StringVar(
            value=self._matching_theme_preset() or "Custom"
        )
        preset = ttk.Combobox(
            inner,
            textvariable=self.theme_preset_var,
            values=list(THEME_PRESETS.keys()) + ["Custom"],
            state="readonly",
            style="Dark.TCombobox",
        )
        preset.pack(fill="x", pady=(0, 22))
        preset.bind("<<ComboboxSelected>>", self._preset_changed)

        grid = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        grid.pack(fill="x")

        items = [
            ("BACKGROUND", "bg"),
            ("PANEL", "panel"),
            ("SECONDARY PANEL", "panel2"),
            ("BORDER", "border"),
            ("TEXT", "text"),
            ("MUTED TEXT", "muted"),
            ("ACCENT", "accent"),
        ]

        for i, (label, key) in enumerate(items):
            card = tk.Frame(
                grid,
                bg=t["panel2"],
                highlightthickness=1,
                highlightbackground=t["border"],
            )
            self._track(card, "panel2", "border")
            card.grid(
                row=i // 2, column=i % 2,
                sticky="nsew", padx=6, pady=6
            )

            name = self._label(
                card, label, ("Segoe UI", 9, "bold"),
                panel2=True,
            )
            name.pack(anchor="w", padx=14, pady=(12, 5))

            btn = tk.Button(
                card,
                text="CHOOSE COLOR",
                command=lambda k=key, l=label.title(): self._choose_color(k, l),
                bg=t["accent"], fg="#07111c",
                activebackground=t["accent"],
                activeforeground="#07111c",
                relief="flat", bd=0,
                font=("Segoe UI", 8, "bold"),
                pady=7,
            )
            btn.pack(fill="x", padx=14, pady=(0, 12))

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        reset = tk.Button(
            inner,
            text="RESET TO INDUSTRIAL ORANGE",
            command=self._reset_theme,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"],
            activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"),
            pady=10,
        )
        reset.pack(fill="x", pady=(22, 0))

    # -------------------- Phrases page --------------------
    def _build_phrases_page(self):
        t = self.theme
        self.phrases_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.phrases_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "PHRASES & KEYBINDS", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            "Commands are grouped by context. Pick a group, choose an action, edit its keybind, then edit the phrases that trigger it.",
            ("Segoe UI", 9), muted=True
        ).pack(anchor="w", pady=(4, 16))

        selectors = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        selectors.pack(fill="x")

        self._label(
            selectors, "GROUP", ("Segoe UI", 8, "bold"), muted=True
        ).grid(row=0, column=0, sticky="w", pady=(0, 5), padx=(0, 8))
        self._label(
            selectors, "ACTION", ("Segoe UI", 8, "bold"), muted=True
        ).grid(row=0, column=1, sticky="w", pady=(0, 5), padx=(8, 0))

        # Friendly grouping so related commands stay together.
        self.phrase_groups = {
            "SHIP COMMANDS": [
                "Ship Power", "Engines & Lights", "Landing & ATC",
                "Quantum", "Power Management", "Flight", "Utility",
                "Mining & Scanning", "Targeting", "Shields",
                "Ship Weapons", "Interface", "Special"
            ],
            "ON FOOT - WEAPONS": ["On Foot - Weapons"],
            "ON FOOT - MOVEMENT": ["On Foot - Movement"],
            "ON FOOT - UTILITY": ["On Foot - Utility", "Interface"],
            # Every user-created action appears here regardless of its
            # custom subcategory.
            "CUSTOM PHRASES": [],
        }

        self.phrase_group_var = tk.StringVar(value="SHIP COMMANDS")
        self.phrase_group_combo = ttk.Combobox(
            selectors,
            textvariable=self.phrase_group_var,
            values=list(self.phrase_groups.keys()),
            state="readonly",
            style="Dark.TCombobox",
        )
        self.phrase_group_combo.grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        self.phrase_group_combo.bind(
            "<<ComboboxSelected>>", self._phrase_group_changed
        )

        self.phrase_action_var = tk.StringVar()
        self.phrase_action_combo = ttk.Combobox(
            selectors,
            textvariable=self.phrase_action_var,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.phrase_action_combo.grid(
            row=1, column=1, sticky="ew", padx=(8, 0)
        )
        self.phrase_action_combo.bind(
            "<<ComboboxSelected>>", self._load_phrase_editor
        )

        selectors.grid_columnconfigure(0, weight=1)
        selectors.grid_columnconfigure(1, weight=2)

        keyrow = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        keyrow.pack(fill="x", pady=(14, 10))

        self._label(
            keyrow, "KEYBIND", ("Segoe UI", 8, "bold"), muted=True
        ).pack(side="left", padx=(0, 8))

        self.phrase_key_var = tk.StringVar()
        self.phrase_key_entry = tk.Entry(
            keyrow,
            textvariable=self.phrase_key_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 10),
        )
        self.phrase_key_entry.pack(
            side="left", fill="x", expand=True, ipady=7
        )

        self.phrase_action_type_label = self._label(
            keyrow, "", ("Segoe UI", 8), muted=True
        )
        self.phrase_action_type_label.pack(side="left", padx=(10, 0))

        self._label(
            inner, "RECOGNIZED PHRASES — ONE PER LINE",
            ("Segoe UI", 8, "bold"), muted=True
        ).pack(anchor="w", pady=(4, 6))

        editor_frame = self._track(
            tk.Frame(inner, bg=t["panel"]), "panel"
        )
        editor_frame.pack(fill="both", expand=True)

        self.phrase_text = tk.Text(
            editor_frame,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", borderwidth=0,
            font=("Cascadia Mono", 10),
            wrap="word", padx=14, pady=12,
        )
        self.phrase_text.pack(
            side="left", fill="both", expand=True
        )

        sb = ttk.Scrollbar(
            editor_frame, command=self.phrase_text.yview
        )
        sb.pack(side="right", fill="y")
        self.phrase_text.configure(yscrollcommand=sb.set)

        self._label(
            inner, "PHRASE → KEYBIND PREVIEW",
            ("Segoe UI", 8, "bold"), muted=True
        ).pack(anchor="w", pady=(10, 6))

        self.phrase_preview = tk.Text(
            inner,
            height=5,
            bg=t["panel2"], fg=t["text"],
            relief="flat", borderwidth=0,
            font=("Cascadia Mono", 9),
            padx=12, pady=8,
            state="disabled",
        )
        self.phrase_preview.pack(fill="x")

        buttons = self._track(
            tk.Frame(inner, bg=t["panel"]), "panel"
        )
        buttons.pack(fill="x", pady=(12, 0))

        save_btn = tk.Button(
            buttons,
            text="SAVE PHRASES + KEYBIND",
            command=self._save_phrase_editor,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"],
            activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), pady=9,
        )
        save_btn.pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )

        reset_btn = tk.Button(
            buttons,
            text="RESET ACTION TO DEFAULT",
            command=self._reset_phrase_editor,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"],
            activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), pady=9,
        )
        self._track(reset_btn, "panel2", "text")
        reset_btn.pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )

        self.phrase_text.bind("<KeyRelease>", lambda e: self._update_phrase_preview())
        self.phrase_key_entry.bind("<KeyRelease>", lambda e: self._update_phrase_preview())

        self._phrase_group_changed()

    def _actions_for_phrase_group(self):
        group = self.phrase_group_var.get()

        if group == "CUSTOM PHRASES":
            return [
                action_id
                for action_id, action in ACTIONS.items()
                if bool(action.get("custom"))
            ]

        categories = set(
            self.phrase_groups.get(group, [])
        )
        return [
            action_id for action_id, action in ACTIONS.items()
            if action["category"] in categories
        ]

    def _refresh_phrase_group_options(self):
        if not hasattr(self, "phrase_group_combo"):
            return
        values = list(self.phrase_groups.keys())
        self.phrase_group_combo["values"] = values
        if self.phrase_group_var.get() not in values:
            self.phrase_group_var.set("SHIP COMMANDS")
        self._phrase_group_changed()

    def _phrase_group_changed(self, *_):
        action_ids = self._actions_for_phrase_group()
        labels = [ACTIONS[a]["label"] for a in action_ids]
        self.phrase_action_lookup = {
            ACTIONS[a]["label"]: a for a in action_ids
        }
        self.phrase_action_combo["values"] = labels
        if labels:
            self.phrase_action_var.set(labels[0])
            self._load_phrase_editor()

    def _selected_phrase_action_id(self):
        return self.phrase_action_lookup[
            self.phrase_action_var.get()
        ]

    def _load_phrase_editor(self, *_):
        action_id = self._selected_phrase_action_id()
        action = ACTIONS[action_id]

        self.phrase_key_var.set(
            self.keybinds.get(action_id, action["key"])
        )

        hold = (
            f"hold {action['hold']:.1f}s"
            if action["type"] == "hold"
            else action["type"]
        )
        self.phrase_action_type_label.configure(
            text=f"Action type: {hold}"
        )

        self.phrase_text.delete("1.0", tk.END)
        self.phrase_text.insert(
            "1.0",
            "\n".join(self.phrases.get(action_id, []))
        )
        self._update_phrase_preview()

    def _update_phrase_preview(self):
        if not hasattr(self, "phrase_preview"):
            return
        key = self.phrase_key_var.get().strip() or "(no key)"
        phrases = [
            line.strip()
            for line in self.phrase_text.get("1.0", tk.END).splitlines()
            if line.strip()
        ]
        lines = [
            f"{phrase}  →  {key}"
            for phrase in phrases
        ]
        self.phrase_preview.configure(state="normal")
        self.phrase_preview.delete("1.0", tk.END)
        self.phrase_preview.insert(
            "1.0", "\n".join(lines)
        )
        self.phrase_preview.configure(state="disabled")

    def _save_phrase_editor(self):
        action_id = self._selected_phrase_action_id()
        raw = self.phrase_text.get("1.0", tk.END)
        keybind = self.phrase_key_var.get().strip().lower()

        phrases = []
        seen = set()
        for line in raw.splitlines():
            phrase = line.strip().lower()
            if phrase and phrase not in seen:
                phrases.append(phrase)
                seen.add(phrase)

        if not phrases:
            messagebox.showerror(
                "Phrases",
                "Keep at least one phrase for this action."
            )
            return

        if not keybind:
            messagebox.showerror(
                "Keybind",
                "Enter a keybind for this action."
            )
            return

        self.phrases[action_id] = phrases
        self.keybinds[action_id] = keybind
        self._save_settings()
        self._refresh_command_list()
        self._update_phrase_preview()

        messagebox.showinfo(
            "Saved",
            f"Saved {len(phrases)} phrase(s) and keybind '{keybind}' "
            f"for {ACTIONS[action_id]['label']}."
        )

    def _reset_phrase_editor(self):
        action_id = self._selected_phrase_action_id()
        self.phrases[action_id] = list(
            DEFAULT_PHRASES.get(action_id, [])
        )
        self.keybinds[action_id] = ACTIONS[action_id]["key"]
        self._save_settings()
        self._load_phrase_editor()
        self._refresh_command_list()

    # -------------------- CUSTOM WORDS page --------------------
    def _build_custom_words_page(self):
        t = self.theme
        self.custom_words_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.custom_words_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "CUSTOM WORDS", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            "Create your own voice action, choose or type a subcategory, assign a keybind, and add as many trigger phrases as you want.",
            ("Segoe UI", 9), muted=True
        ).pack(anchor="w", pady=(4, 16))

        form = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        form.pack(fill="x")

        self._label(form, "ACTION NAME", ("Segoe UI", 8, "bold"), muted=True).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 5))
        self._label(form, "SUBCATEGORY", ("Segoe UI", 8, "bold"), muted=True).grid(row=0, column=1, sticky="w", padx=(8, 8), pady=(0, 5))
        self._label(form, "KEYBIND", ("Segoe UI", 8, "bold"), muted=True).grid(row=0, column=2, sticky="w", padx=(8, 0), pady=(0, 5))

        self.custom_name_var = tk.StringVar()
        self.custom_name_entry = tk.Entry(
            form, textvariable=self.custom_name_var,
            bg=t["panel2"], fg=t["text"], insertbackground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 10)
        )
        self.custom_name_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8), ipady=8)

        categories = sorted({a["category"] for a in ACTIONS.values()} | {"Custom"})
        self.custom_category_var = tk.StringVar(value="Custom")
        self.custom_category_combo = ttk.Combobox(
            form,
            textvariable=self.custom_category_var,
            values=categories,
            state="normal",
            style="Dark.TCombobox",
        )
        self.custom_category_combo.grid(row=1, column=1, sticky="ew", padx=8)

        self.custom_key_var = tk.StringVar()
        self.custom_key_entry = tk.Entry(
            form, textvariable=self.custom_key_var,
            bg=t["panel2"], fg=t["text"], insertbackground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 10)
        )
        self.custom_key_entry.grid(row=1, column=2, sticky="ew", padx=(8, 0), ipady=8)

        form.grid_columnconfigure(0, weight=2)
        form.grid_columnconfigure(1, weight=2)
        form.grid_columnconfigure(2, weight=1)

        type_row = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        type_row.pack(fill="x", pady=(12, 10))

        self._label(type_row, "ACTION TYPE", ("Segoe UI", 8, "bold"), muted=True).pack(side="left", padx=(0, 8))
        self.custom_type_var = tk.StringVar(value="tap")
        for value, label in (("tap", "Tap"), ("hold", "Hold")):
            rb = tk.Radiobutton(
                type_row, text=label, value=value,
                variable=self.custom_type_var,
                bg=t["panel"], fg=t["text"],
                selectcolor=t["panel2"],
                activebackground=t["panel"], activeforeground=t["text"],
                font=("Segoe UI", 8)
            )
            rb.pack(side="left", padx=(0, 10))

        self._label(type_row, "HOLD SECONDS", ("Segoe UI", 8, "bold"), muted=True).pack(side="left", padx=(10, 8))
        self.custom_hold_var = tk.StringVar(value="1.0")
        self.custom_hold_entry = tk.Entry(
            type_row, textvariable=self.custom_hold_var,
            width=8,
            bg=t["panel2"], fg=t["text"], insertbackground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 9)
        )
        self.custom_hold_entry.pack(side="left", ipady=5)

        self._label(
            inner, "CUSTOM PHRASES — CHECKED PHRASES WILL BE ACTIVE",
            ("Segoe UI", 8, "bold"), muted=True
        ).pack(anchor="w", pady=(6, 6))

        addrow = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        addrow.pack(fill="x")

        self.custom_phrase_var = tk.StringVar()
        self.custom_phrase_entry = tk.Entry(
            addrow, textvariable=self.custom_phrase_var,
            bg=t["panel2"], fg=t["text"], insertbackground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 10)
        )
        self.custom_phrase_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.custom_phrase_entry.bind("<Return>", lambda e: self._add_custom_phrase_row())

        addbtn = tk.Button(
            addrow, text="ADD PHRASE",
            command=self._add_custom_phrase_row,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0, font=("Segoe UI", 8, "bold"),
            padx=16, pady=8
        )
        addbtn.pack(side="left", padx=(10, 0))

        checklist_outer = self._track(tk.Frame(inner, bg=t["panel2"]), "panel2")
        checklist_outer.pack(fill="both", expand=True, pady=(10, 10))

        self.custom_phrase_canvas = tk.Canvas(
            checklist_outer, bg=t["panel2"], highlightthickness=0
        )
        self.custom_phrase_canvas.pack(side="left", fill="both", expand=True)

        cscroll = ttk.Scrollbar(
            checklist_outer, orient="vertical",
            command=self.custom_phrase_canvas.yview
        )
        cscroll.pack(side="right", fill="y")
        self.custom_phrase_canvas.configure(yscrollcommand=cscroll.set)

        self.custom_phrase_check_frame = self._track(
            tk.Frame(self.custom_phrase_canvas, bg=t["panel2"]), "panel2"
        )
        self.custom_phrase_canvas.create_window(
            (0, 0), window=self.custom_phrase_check_frame,
            anchor="nw"
        )
        self.custom_phrase_check_frame.bind(
            "<Configure>",
            lambda e: self.custom_phrase_canvas.configure(
                scrollregion=self.custom_phrase_canvas.bbox("all")
            )
        )
        self.custom_phrase_rows = []

        bottom = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        bottom.pack(fill="x")

        create_btn = tk.Button(
            bottom, text="CREATE CUSTOM COMMAND",
            command=self._create_custom_command,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0, font=("Segoe UI", 9, "bold"), pady=9
        )
        create_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        clear_btn = tk.Button(
            bottom, text="CLEAR FORM",
            command=self._clear_custom_word_form,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0, font=("Segoe UI", 9, "bold"), pady=9
        )
        self._track(clear_btn, "panel2", "text")
        clear_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self._label(
            inner, "EXISTING CUSTOM COMMANDS",
            ("Segoe UI", 8, "bold"), muted=True
        ).pack(anchor="w", pady=(14, 6))

        custom_manage = self._track(
            tk.Frame(inner, bg=t["panel"]), "panel"
        )
        custom_manage.pack(fill="x")

        self.custom_existing_list = tk.Listbox(
            custom_manage,
            height=6,
            bg=t["panel2"], fg=t["text"],
            selectbackground=t["border"], selectforeground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 9),
            highlightthickness=0
        )
        self.custom_existing_list.pack(side="left", fill="both", expand=True)
        self.custom_existing_list.bind(
            "<<ListboxSelect>>",
            self._custom_existing_selected
        )

        custom_manage_right = self._track(
            tk.Frame(custom_manage, bg=t["panel"]), "panel"
        )
        custom_manage_right.pack(side="right", fill="both", padx=(10, 0))

        self._label(
            custom_manage_right,
            "PHRASES IN SELECTED COMMAND",
            ("Segoe UI", 8, "bold"),
            muted=True
        ).pack(anchor="w", pady=(0, 5))

        self.custom_existing_phrase_list = tk.Listbox(
            custom_manage_right,
            width=42,
            height=5,
            bg=t["panel2"], fg=t["text"],
            selectbackground=t["border"], selectforeground=t["text"],
            relief="flat", bd=0, font=("Cascadia Mono", 9),
            highlightthickness=0
        )
        self.custom_existing_phrase_list.pack(fill="both", expand=True)

        delete_phrase_btn = tk.Button(
            custom_manage_right,
            text="DELETE SELECTED PHRASE",
            command=self._delete_selected_custom_phrase,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), pady=7
        )
        self._track(delete_phrase_btn, "panel2", "text")
        delete_phrase_btn.pack(fill="x", pady=(8, 4))

        delete_command_btn = tk.Button(
            custom_manage_right,
            text="DELETE CUSTOM COMMAND",
            command=self._delete_selected_custom_command,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), pady=7
        )
        self._track(delete_command_btn, "panel2", "text")
        delete_command_btn.pack(fill="x")

        self.custom_existing_action_ids = []
        self.custom_selected_action_id = None
        self._refresh_custom_existing_list()

    def _add_custom_phrase_row(self):
        phrase = self.custom_phrase_var.get().strip().lower()
        if not phrase:
            return

        if any(row["phrase"] == phrase for row in self.custom_phrase_rows):
            self.custom_phrase_var.set("")
            return

        var = tk.BooleanVar(value=True)
        t = self.theme
        row_frame = self._track(
            tk.Frame(self.custom_phrase_check_frame, bg=t["panel2"]), "panel2"
        )
        row_frame.pack(fill="x", padx=8, pady=3)

        cb = tk.Checkbutton(
            row_frame,
            text=phrase,
            variable=var,
            anchor="w",
            bg=t["panel2"], fg=t["text"],
            selectcolor=t["panel2"],
            activebackground=t["panel2"], activeforeground=t["text"],
            font=("Cascadia Mono", 9)
        )
        cb.pack(side="left", fill="x", expand=True)

        remove = tk.Button(
            row_frame, text="REMOVE",
            command=lambda p=phrase: self._remove_custom_phrase_row(p),
            bg=t["panel2"], fg=t["muted"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0, font=("Segoe UI", 7, "bold")
        )
        remove.pack(side="right")

        self.custom_phrase_rows.append({
            "phrase": phrase,
            "var": var,
            "frame": row_frame,
        })
        self.custom_phrase_var.set("")

    def _remove_custom_phrase_row(self, phrase):
        for row in list(self.custom_phrase_rows):
            if row["phrase"] == phrase:
                try:
                    row["frame"].destroy()
                except Exception:
                    pass
                self.custom_phrase_rows.remove(row)
                break

    def _clear_custom_word_form(self):
        self.custom_name_var.set("")
        self.custom_category_var.set("Custom")
        self.custom_key_var.set("")
        self.custom_type_var.set("tap")
        self.custom_hold_var.set("1.0")
        self.custom_phrase_var.set("")
        for row in list(self.custom_phrase_rows):
            try:
                row["frame"].destroy()
            except Exception:
                pass
        self.custom_phrase_rows.clear()

    def _slugify_custom_action(self, text):
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        base = "custom_" + (slug or "command")
        action_id = base
        n = 2
        while action_id in ACTIONS:
            action_id = f"{base}_{n}"
            n += 1
        return action_id

    def _create_custom_command(self):
        label = self.custom_name_var.get().strip()
        category = self.custom_category_var.get().strip() or "Custom"
        key = self.custom_key_var.get().strip().lower()
        action_type = self.custom_type_var.get().strip().lower()

        phrases = [
            row["phrase"]
            for row in self.custom_phrase_rows
            if bool(row["var"].get())
        ]

        if not label:
            messagebox.showerror("Custom Words", "Enter an action name.")
            return
        if not key:
            messagebox.showerror("Custom Words", "Enter a keybind.")
            return
        if not phrases:
            messagebox.showerror("Custom Words", "Add and check at least one phrase.")
            return

        hold = None
        if action_type == "hold":
            try:
                hold = float(self.custom_hold_var.get())
                if hold <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Custom Words", "Hold seconds must be a positive number.")
                return

        action_id = self._slugify_custom_action(label)
        record = {
            "id": action_id,
            "label": label,
            "category": category,
            "key": key,
            "type": action_type,
            "hold": hold,
            "phrases": phrases,
        }

        self.custom_actions.append(record)
        ACTIONS[action_id] = {
            "label": label,
            "category": category,
            "type": action_type,
            "key": key,
            "hold": hold,
            "custom": True,
        }
        DEFAULT_PHRASES[action_id] = list(phrases)
        self.phrases[action_id] = list(phrases)
        self.keybinds[action_id] = key

        self._save_settings()
        self._refresh_custom_existing_list()
        self._refresh_keybind_search()
        self._refresh_command_list()
        self._refresh_phrase_group_options()

        # Make new category available in phrase group custom selectors next launch,
        # and immediately available in the KEYBINDS search.
        messagebox.showinfo(
            "Custom Command Created",
            f"{label} created with {len(phrases)} active phrase(s)."
        )
        self._clear_custom_word_form()

    def _refresh_custom_existing_list(self):
        if not hasattr(self, "custom_existing_list"):
            return

        self.custom_existing_list.delete(0, tk.END)
        self.custom_existing_action_ids = []

        for item in self.custom_actions:
            action_id = item.get("id", "")
            label = item.get("label", "Custom Command")
            key = self.keybinds.get(action_id, item.get("key", ""))
            category = item.get("category", "Custom")
            phrases = self.phrases.get(action_id, item.get("phrases", []))

            self.custom_existing_list.insert(
                tk.END,
                f"{category:<20}  {label:<28}  → {key:<12}  {len(phrases)} phrase(s)"
            )
            self.custom_existing_action_ids.append(action_id)

        self.custom_selected_action_id = None
        if hasattr(self, "custom_existing_phrase_list"):
            self.custom_existing_phrase_list.delete(0, tk.END)

    def _custom_existing_selected(self, *_):
        sel = self.custom_existing_list.curselection()
        if not sel:
            return

        action_id = self.custom_existing_action_ids[sel[0]]
        self.custom_selected_action_id = action_id

        self.custom_existing_phrase_list.delete(0, tk.END)
        for phrase in self.phrases.get(action_id, []):
            self.custom_existing_phrase_list.insert(tk.END, phrase)

    def _delete_selected_custom_phrase(self):
        action_id = self.custom_selected_action_id
        if not action_id:
            messagebox.showerror(
                "Custom Words",
                "Select a custom command first."
            )
            return

        phrase_sel = self.custom_existing_phrase_list.curselection()
        if not phrase_sel:
            messagebox.showerror(
                "Custom Words",
                "Select a phrase to delete."
            )
            return

        current = list(self.phrases.get(action_id, []))
        if len(current) <= 1:
            messagebox.showerror(
                "Custom Words",
                "A custom command must keep at least one phrase. "
                "Delete the entire custom command instead."
            )
            return

        phrase = current[phrase_sel[0]]
        if not messagebox.askyesno(
            "Delete Phrase",
            f'Delete the custom phrase "{phrase}"?'
        ):
            return

        current.remove(phrase)
        self.phrases[action_id] = current
        DEFAULT_PHRASES[action_id] = list(current)

        for item in self.custom_actions:
            if item.get("id") == action_id:
                item["phrases"] = list(current)
                break

        self._save_settings()
        self._refresh_custom_existing_list()
        self._refresh_keybind_search()
        self._refresh_phrase_group_options()

        if action_id in self.custom_existing_action_ids:
            idx = self.custom_existing_action_ids.index(action_id)
            self.custom_existing_list.selection_set(idx)
            self.custom_existing_list.see(idx)
            self._custom_existing_selected()

    def _delete_selected_custom_command(self):
        action_id = self.custom_selected_action_id
        if not action_id:
            messagebox.showerror(
                "Custom Words",
                "Select a custom command first."
            )
            return

        label = ACTIONS.get(action_id, {}).get("label", "this custom command")
        if not messagebox.askyesno(
            "Delete Custom Command",
            f'Delete "{label}" and all of its custom phrases?'
        ):
            return

        self.custom_actions = [
            item for item in self.custom_actions
            if item.get("id") != action_id
        ]
        ACTIONS.pop(action_id, None)
        DEFAULT_PHRASES.pop(action_id, None)
        self.phrases.pop(action_id, None)
        self.keybinds.pop(action_id, None)
        self.last_triggered.pop(action_id, None)

        self._save_settings()
        self._refresh_custom_existing_list()
        self._refresh_keybind_search()
        self._refresh_command_list()
        self._refresh_phrase_group_options()

    # -------------------- KEYBINDS page --------------------
    def _build_keybinds_page(self):
        t = self.theme
        self.keybinds_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.keybinds_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "KEYBINDS", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            "Type anything to search normally, or type K, I, F12, alt+f4, etc. and press FILTER BY KEYBIND to show only actions actually assigned to that exact key.",
            ("Segoe UI", 9), muted=True
        ).pack(anchor="w", pady=(4, 16))

        searchrow = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        searchrow.pack(fill="x")

        self.keybind_search_var = tk.StringVar()
        self.keybind_filter_mode = False
        self.keybind_search_entry = tk.Entry(
            searchrow,
            textvariable=self.keybind_search_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 10),
        )
        self.keybind_search_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.keybind_search_entry.bind("<KeyRelease>", self._keybind_search_typed)

        filter_btn = tk.Button(
            searchrow, text="FILTER BY KEYBIND",
            command=self._apply_keybind_only_filter,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), padx=14, pady=8
        )
        filter_btn.pack(side="left", padx=(10, 0))

        search_all_btn = tk.Button(
            searchrow, text="SEARCH ALL",
            command=self._apply_keybind_general_search,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), padx=14, pady=8
        )
        self._track(search_all_btn, "panel2", "text")
        search_all_btn.pack(side="left", padx=(8, 0))

        clear_btn = tk.Button(
            searchrow, text="CLEAR",
            command=self._clear_keybind_search,
            bg=t["panel2"], fg=t["text"],
            activebackground=t["border"], activeforeground=t["text"],
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"), padx=14, pady=8
        )
        self._track(clear_btn, "panel2", "text")
        clear_btn.pack(side="left", padx=(8, 0))

        body = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        body.pack(fill="both", expand=True, pady=(14, 12))

        left = self._track(tk.Frame(body, bg=t["panel"]), "panel")
        left.pack(side="left", fill="both", expand=True)

        self.keybind_search_list = tk.Listbox(
            left,
            bg=t["panel2"], fg=t["text"],
            selectbackground=t["border"], selectforeground=t["text"],
            relief="flat", bd=0,
            activestyle="none",
            font=("Cascadia Mono", 9),
            highlightthickness=0,
        )
        self.keybind_search_list.pack(fill="both", expand=True)
        self.keybind_search_list.bind("<<ListboxSelect>>", self._keybind_search_selected)

        right = self._track(tk.Frame(body, bg=t["panel"], width=330), "panel")
        right.pack(side="right", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        self._label(right, "SELECTED ACTION", ("Segoe UI", 8, "bold"), muted=True).pack(anchor="w")
        self.keybind_selected_label = self._label(right, "None", ("Segoe UI", 11, "bold"))
        self.keybind_selected_label.pack(anchor="w", pady=(5, 14))

        self._label(right, "KEYBIND", ("Segoe UI", 8, "bold"), muted=True).pack(anchor="w")
        self.keybind_edit_var = tk.StringVar()
        self.keybind_edit_entry = tk.Entry(
            right,
            textvariable=self.keybind_edit_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 10),
        )
        self.keybind_edit_entry.pack(fill="x", ipady=8, pady=(5, 10))

        self.keybind_phrase_preview = tk.Text(
            right, height=10,
            bg=t["panel2"], fg=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 9),
            padx=10, pady=8,
            state="disabled",
        )
        self.keybind_phrase_preview.pack(fill="both", expand=True, pady=(0, 10))

        save = tk.Button(
            right, text="SAVE KEYBIND",
            command=self._save_keybind_search_edit,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), pady=9
        )
        save.pack(fill="x")

        self.keybind_search_action_ids = []
        self.keybind_selected_action_id = None
        self._refresh_keybind_search()

    def _keybind_search_typed(self, *_):
        self.keybind_filter_mode = False
        self._refresh_keybind_search()

    def _apply_keybind_only_filter(self):
        self.keybind_filter_mode = True
        self._refresh_keybind_search()

    def _apply_keybind_general_search(self):
        self.keybind_filter_mode = False
        self._refresh_keybind_search()

    def _clear_keybind_search(self):
        self.keybind_search_var.set("")
        self.keybind_filter_mode = False
        self._refresh_keybind_search()

    def _normalize_filter_key(self, value):
        value = value.strip().lower()
        aliases = {
            "ctrl": "left control",
            "control": "left control",
            "shift": "left shift",
            "alt f4": "alt+f4",
            "spacebar": "space",
            "space bar": "space",
        }
        return aliases.get(value, value)

    def _refresh_keybind_search(self):
        if not hasattr(self, "keybind_search_list"):
            return

        q = self.keybind_search_var.get().strip().lower()
        filter_key = self._normalize_filter_key(q)

        self.keybind_search_list.delete(0, tk.END)
        self.keybind_search_action_ids = []

        for action_id, action in ACTIONS.items():
            key = self.keybinds.get(
                action_id, action["key"]
            ).strip().lower()
            phrases = self.phrases.get(action_id, [])

            if self.keybind_filter_mode:
                # Strict: only the actual assigned keybind can match.
                if not filter_key or key != filter_key:
                    continue
            else:
                haystack = " ".join([
                    action["label"],
                    action["category"],
                    key,
                    *phrases
                ]).lower()
                if q and q not in haystack:
                    continue

            canonical = phrases[0] if phrases else ""
            line = (
                f"{key:<22}  "
                f"{action['label']:<30}  "
                f"{canonical}"
            )
            self.keybind_search_list.insert(tk.END, line)
            self.keybind_search_action_ids.append(action_id)

    def _keybind_search_selected(self, *_):
        sel = self.keybind_search_list.curselection()
        if not sel:
            return
        action_id = self.keybind_search_action_ids[sel[0]]
        self.keybind_selected_action_id = action_id
        action = ACTIONS[action_id]
        key = self.keybinds.get(action_id, action["key"])

        self.keybind_selected_label.configure(text=action["label"])
        self.keybind_edit_var.set(key)

        phrases = self.phrases.get(action_id, [])
        self.keybind_phrase_preview.configure(state="normal")
        self.keybind_phrase_preview.delete("1.0", tk.END)
        self.keybind_phrase_preview.insert(
            "1.0",
            "\n".join(f"{p}  →  {key}" for p in phrases)
        )
        self.keybind_phrase_preview.configure(state="disabled")

    def _save_keybind_search_edit(self):
        action_id = self.keybind_selected_action_id
        if not action_id:
            messagebox.showerror("Keybinds", "Select an action first.")
            return

        key = self.keybind_edit_var.get().strip().lower()
        if not key:
            messagebox.showerror("Keybinds", "Enter a keybind.")
            return

        self.keybinds[action_id] = key
        self._save_settings()
        self._refresh_keybind_search()
        self._refresh_command_list()
        self._keybind_search_selected()
        messagebox.showinfo(
            "Keybind Saved",
            f"{ACTIONS[action_id]['label']} is now bound to {key}."
        )

    # -------------------- MINING MODE page --------------------
    def _build_mining_page(self):
        t = self.theme
        self.mining_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.mining_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(
            tk.Frame(panel, bg=t["panel"]), "panel"
        )
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "MINING MODE", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            'Reverse lookup: ask "what resource is 4,270?" and the app will identify the ore and signature multiple. The table stays here for reference.',
            ("Segoe UI", 9),
            muted=True,
        ).pack(anchor="w", pady=(4, 14))

        controls = self._track(
            tk.Frame(inner, bg=t["panel"]), "panel"
        )
        controls.pack(fill="x", pady=(0, 12))

        self.mining_ore_var = tk.StringVar(value="iron")
        ore_combo = ttk.Combobox(
            controls,
            textvariable=self.mining_ore_var,
            values=MINING_DISPLAY_ORDER,
            state="readonly",
            style="Dark.TCombobox",
        )
        ore_combo.pack(side="left", fill="x", expand=True)

        speak_btn = tk.Button(
            controls,
            text="READ SIGNATURES",
            command=self._speak_selected_mining,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"],
            activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=16, pady=8,
        )
        speak_btn.pack(side="left", padx=(10, 0))

        location_row = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        location_row.pack(fill="x", pady=(0, 12))

        self.mining_location_var = tk.StringVar(value="iron")
        self.mining_location_entry = tk.Entry(
            location_row,
            textvariable=self.mining_location_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 10),
        )
        self.mining_location_entry.pack(side="left", fill="x", expand=True, ipady=8)

        find_locations = tk.Button(
            location_row,
            text="WHERE CAN I MINE THIS?",
            command=self._mining_location_button,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), padx=16, pady=8,
        )
        find_locations.pack(side="left", padx=(10, 0))

        self.mining_location_result = self._label(
            inner, "", ("Segoe UI", 9), muted=True
        )
        self.mining_location_result.pack(anchor="w", fill="x", pady=(0, 10))

        self.mining_table = tk.Text(
            inner,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", borderwidth=0,
            font=("Cascadia Mono", 9),
            wrap="none",
            padx=14, pady=12,
            state="disabled",
        )
        self.mining_table.pack(fill="both", expand=True)

        lines = []
        lines.append(
            f"{'ORE':<16} {'1x':>8} {'2x':>8} {'3x':>8} {'4x':>8} {'5x':>8} {'6x':>8} {'7x':>8} {'8x':>8} {'9x':>8} {'10x':>8}"
        )
        lines.append("-" * 108)

        for ore in MINING_DISPLAY_ORDER:
            base = MINING_PRIMARY[ore]
            vals = [base * i for i in range(1, 11)]
            lines.append(
                f"{ore.title():<16}" +
                "".join(f"{v:>8,}" for v in vals)
            )

        self.mining_table.configure(state="normal")
        self.mining_table.insert("1.0", "\n".join(lines))
        self.mining_table.configure(state="disabled")

    def _mining_values(self, ore):
        base = MINING_PRIMARY[ore]
        return [base * i for i in range(1, 11)]

    def _mining_tts_text(self, ore):
        vals = self._mining_values(ore)
        spoken = ", ".join(
            f"{i} X, {v:,}"
            for i, v in enumerate(vals, start=1)
        )
        return f"{ore.title()} mining signatures are: {spoken}."

    def _speak_selected_mining(self):
        ore = self.mining_ore_var.get().lower()
        self._speak(self._mining_tts_text(ore), force=True)
        self._history_add(
            f"Mining signatures requested for {ore.title()}."
        )

    def _reverse_mining_matches(self, signature):
        matches = []
        for ore in MINING_DISPLAY_ORDER:
            base = MINING_PRIMARY[ore]
            for multiple in range(1, 11):
                if base * multiple == signature:
                    matches.append((ore, multiple, signature))
        return matches

    def _nearest_mining_match(self, signature):
        best = None
        for ore in MINING_DISPLAY_ORDER:
            base = MINING_PRIMARY[ore]
            for multiple in range(1, 11):
                value = base * multiple
                diff = abs(value - signature)
                if best is None or diff < best[0]:
                    best = (diff, ore, multiple, value)
        return best

    def _extract_signature_question(self, heard):
        """
        Reverse mining lookup.
        Examples:
          what resource is 4,250
          what ore is 4270
          resource for signature 8550
          what mineral is signature 12,810
        """
        normalized = heard.lower()

        question_words = (
            "what resource",
            "which resource",
            "what ore",
            "which ore",
            "what mineral",
            "which mineral",
            "resource is",
            "ore is",
            "signature is",
            "signature for",
            "resource for",
        )
        if not any(q in normalized for q in question_words):
            return None

        # Prefer values >= 1,000 so unrelated small numbers don't trigger.
        numbers = re.findall(r"\b\d[\d,]*\b", normalized)
        for raw in reversed(numbers):
            try:
                value = int(raw.replace(",", ""))
            except ValueError:
                continue
            if value >= 1000:
                return value
        return None

    def _reverse_mining_tts_text(self, signature):
        matches = self._reverse_mining_matches(signature)

        if matches:
            if len(matches) == 1:
                ore, multiple, value = matches[0]
                return (
                    f"{signature:,} is {ore.title()}, "
                    f"at {multiple} X signature."
                )

            descriptions = [
                f"{ore.title()} at {multiple} X"
                for ore, multiple, _ in matches
            ]
            return (
                f"{signature:,} has multiple matches: "
                + ", ".join(descriptions)
                + "."
            )

        nearest = self._nearest_mining_match(signature)
        if nearest is None:
            return f"I could not find a mining resource for {signature:,}."

        diff, ore, multiple, value = nearest

        # Useful tolerance for numbers that were read/remembered a little off.
        if diff <= 50:
            return (
                f"There is no exact match for {signature:,}. "
                f"The closest is {ore.title()} at {multiple} X, "
                f"with a signature of {value:,}."
            )

        return (
            f"There is no mining signature match for {signature:,}. "
            f"The nearest is {ore.title()} at {multiple} X, "
            f"with {value:,}."
        )


    # -------------------- live Star Citizen data --------------------
    def _http_json(self, url, timeout=10):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "StarCitizenVoiceKeybinds/10.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _mining_location_button(self):
        resource = self.mining_location_var.get().strip().lower()
        if not resource:
            return

        self.mining_location_result.configure(text="Searching...")
        threading.Thread(
            target=self._mining_location_worker,
            args=(resource, False),
            daemon=True,
        ).start()

    def _mining_location_worker(self, resource, speak=True):
        try:
            locations = self._fetch_mining_locations(resource)
            if locations:
                shown = locations[:10]
                answer = (
                    f"{resource.title()} can be mined at "
                    + ", ".join(shown)
                    + "."
                )
            else:
                answer = f"I could not find mining locations for {resource.title()}."
        except Exception:
            fallback = MINING_LOCATION_FALLBACK.get(resource, [])
            if fallback:
                shown = fallback[:10]
                answer = (
                    f"Live lookup failed. Known {resource.title()} mining hotspots include "
                    + ", ".join(shown)
                    + "."
                )
            else:
                answer = f"I could not find mining locations for {resource.title()}."

        self.events.put(("mining_locations", (resource, answer)))
        if speak:
            self._speak(answer, force=True)

    def _fetch_mining_locations(self, resource):
        url = (
            f"{SHIP_API_BASE}/commodities/"
            + urllib.parse.quote(resource)
        )
        payload = self._http_json(url)
        data = payload.get("data", payload)

        names = []

        def walk(obj, path=""):
            if isinstance(obj, dict):
                lower_path = path.lower()

                # Commodity location objects usually contain names plus type/system metadata.
                candidate = None
                for key in ("name", "display_name", "location_name"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        candidate = value.strip()
                        break

                if candidate and (
                    "location" in lower_path
                    or "starmap" in lower_path
                    or "resource" in lower_path
                ):
                    bad = {
                        resource.lower(),
                        "mineable",
                        "mining",
                    }
                    if candidate.lower() not in bad and candidate not in names:
                        names.append(candidate)

                for k, v in obj.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, f"{path}[{i}]")

        walk(data, "data")

        # If the API schema changes and generic traversal returns too many nested names,
        # prefer plausible planetary/moon/ring names by de-duplicating while preserving order.
        cleaned = []
        for name in names:
            if name not in cleaned and len(name) <= 80:
                cleaned.append(name)

        if resource == "iron" and not cleaned:
            cleaned = list(MINING_LOCATION_FALLBACK["iron"])

        return cleaned

    # -------------------- SHIP FINDER page --------------------
    def _build_ship_finder_page(self):
        t = self.theme
        self.ship_finder_page = self._track(
            tk.Frame(self.page_host, bg=t["bg"]), "bg"
        )

        panel = self._panel(self.ship_finder_page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=28, pady=24)

        self._label(
            inner, "SHIP FINDER", ("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        self._label(
            inner,
            "Search a ship to see current in-game purchase and rental locations/prices from the Star Citizen Wiki community API.",
            ("Segoe UI", 9), muted=True
        ).pack(anchor="w", pady=(4, 16))

        row = self._track(tk.Frame(inner, bg=t["panel"]), "panel")
        row.pack(fill="x", pady=(0, 12))

        self.ship_search_var = tk.StringVar(value="Cutlass Black")
        self.ship_search_entry = tk.Entry(
            row,
            textvariable=self.ship_search_var,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 10),
        )
        self.ship_search_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.ship_search_entry.bind("<Return>", lambda e: self._search_ship())

        search_btn = tk.Button(
            row, text="SEARCH",
            command=self._search_ship,
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), padx=18, pady=8,
        )
        search_btn.pack(side="left", padx=(10, 0))

        self.ship_results = tk.Text(
            inner,
            bg=t["panel2"], fg=t["text"],
            insertbackground=t["text"],
            relief="flat", bd=0,
            font=("Cascadia Mono", 9),
            wrap="word",
            padx=14, pady=12,
            state="disabled",
        )
        self.ship_results.pack(fill="both", expand=True)

        self.ship_source_label = self._label(
            inner,
            "Source: api.star-citizen.wiki • live internet connection required",
            ("Segoe UI", 8), muted=True
        )
        self.ship_source_label.pack(anchor="w", pady=(8, 0))

    def _search_ship(self):
        query = self.ship_search_var.get().strip()
        if not query:
            return
        self._set_ship_results(f"Searching for {query}...")
        threading.Thread(
            target=self._ship_search_worker,
            args=(query,),
            daemon=True,
        ).start()

    def _set_ship_results(self, text):
        self.ship_results.configure(state="normal")
        self.ship_results.delete("1.0", tk.END)
        self.ship_results.insert("1.0", text)
        self.ship_results.configure(state="disabled")

    def _ship_search_worker(self, query):
        try:
            result = self._fetch_ship_data(query)
            self.events.put(("ship_search_result", result))
        except Exception as exc:
            self.events.put((
                "ship_search_result",
                f"Ship search failed: {exc}\n\n"
                "The live community API may be unavailable. Try again later."
            ))

    def _fetch_ship_data(self, query):
        params = urllib.parse.urlencode({
            "filter[name]": query,
            "page[size]": 20,
        })
        search_url = f"{SHIP_API_BASE}/vehicles?{params}"
        payload = self._http_json(search_url)
        vehicles = payload.get("data", [])
        if not vehicles:
            return f'No vehicle found for "{query}".'

        q = query.lower()
        vehicle = min(
            vehicles,
            key=lambda v: (
                0 if str(v.get("name", "")).lower() == q else 1,
                abs(len(str(v.get("name", ""))) - len(query)),
            ),
        )

        identifier = vehicle.get("uuid") or vehicle.get("class_name") or vehicle.get("name")
        detail_url = f"{SHIP_API_BASE}/vehicles/{urllib.parse.quote(str(identifier))}"
        detail_payload = self._http_json(detail_url)
        data = detail_payload.get("data", detail_payload)

        name = data.get("name") or vehicle.get("name") or query
        manufacturer = data.get("manufacturer", {})
        if isinstance(manufacturer, dict):
            manufacturer = manufacturer.get("name", "")
        manufacturer = manufacturer or ""

        purchase, rental = self._extract_vehicle_prices(data)

        lines = []
        lines.append(name.upper())
        if manufacturer:
            lines.append(f"Manufacturer: {manufacturer}")
        lines.append("")

        if purchase:
            lines.append("BUY")
            for entry in purchase[:12]:
                lines.append(self._format_vehicle_price_entry(entry))
        else:
            lines.append("BUY")
            lines.append("  No purchase locations found in the current live response.")

        lines.append("")
        if rental:
            lines.append("RENT")
            for entry in rental[:20]:
                lines.append(self._format_vehicle_price_entry(entry))
        else:
            lines.append("RENT")
            lines.append("  No rental locations found in the current live response.")

        # Reliable fallback snapshot for the requested Cutlass Black example.
        if name.lower() == "cutlass black" and not purchase:
            lines += [
                "",
                "CUTLASS BLACK FALLBACK SNAPSHOT (4.10)",
                "  BUY • New Deal - Teasa Spaceport - Lorville • 2,010,960 aUEC",
            ]
        if name.lower() == "cutlass black" and not rental:
            lines += [
                "  RENT • Vantage Rentals - Lorville • 50,274 aUEC",
                "  RENT • Traveler Baijini / Tressler and multiple Vantage locations • about 52,920 aUEC",
            ]

        lines += [
            "",
            "Live community data can change with patches and player-submitted shop updates."
        ]
        return "\n".join(lines)

    def _extract_vehicle_prices(self, data):
        purchase = []
        rental = []
        seen = set()

        def flatten_strings(obj):
            out = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (str, int, float)):
                        out.append(f"{k}:{v}")
                    elif isinstance(v, (dict, list)):
                        out.extend(flatten_strings(v))
            elif isinstance(obj, list):
                for v in obj:
                    out.extend(flatten_strings(v))
            return out

        def walk(obj, path=""):
            if isinstance(obj, dict):
                text = " ".join(flatten_strings(obj)).lower()
                price = None
                for key in ("price", "price_buy", "price_rent", "buy_price", "rent_price"):
                    val = obj.get(key)
                    if isinstance(val, (int, float)) and val > 0:
                        price = val
                        break

                kind = None
                marker = (path + " " + text).lower()
                if any(x in marker for x in ("vehicle_rental", "rental", " rent")):
                    kind = "rent"
                elif any(x in marker for x in ("vehicle_purchase", "purchase", "buy")):
                    kind = "buy"

                if price and kind:
                    sig = (kind, price, marker[:400])
                    if sig not in seen:
                        seen.add(sig)
                        entry = dict(obj)
                        entry["_price"] = price
                        if kind == "buy":
                            purchase.append(entry)
                        else:
                            rental.append(entry)

                for k, v in obj.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, f"{path}[{i}]")

        walk(data, "data")
        return purchase, rental

    def _format_vehicle_price_entry(self, entry):
        price = entry.get("_price") or entry.get("price") or 0

        def find_name(obj, preferred_keys):
            if isinstance(obj, dict):
                for key in preferred_keys:
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
                    if isinstance(val, dict):
                        sub = val.get("name") or val.get("display_name")
                        if isinstance(sub, str) and sub.strip():
                            return sub.strip()
                for v in obj.values():
                    found = find_name(v, preferred_keys)
                    if found:
                        return found
            elif isinstance(obj, list):
                for v in obj:
                    found = find_name(v, preferred_keys)
                    if found:
                        return found
            return ""

        terminal = find_name(entry, ("terminal", "terminal_name", "shop", "store"))
        location = find_name(entry, ("location", "location_name", "city", "planet", "moon", "system"))

        parts = []
        if terminal:
            parts.append(terminal)
        if location and location != terminal:
            parts.append(location)
        if price:
            parts.append(f"{int(price):,} aUEC")
        return "  • " + " • ".join(parts or ["Location data unavailable"])

    # -------------------- RADIO / LINKS pages --------------------
    def _build_link_page(self, title, description, button_text, url):
        t = self.theme
        page = self._track(tk.Frame(self.page_host, bg=t["bg"]), "bg")
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)

        inner = self._track(tk.Frame(panel, bg=t["panel"]), "panel")
        inner.pack(fill="both", expand=True, padx=36, pady=34)

        self._label(inner, title, ("Segoe UI", 20, "bold")).pack(anchor="w")
        self._label(
            inner, description, ("Segoe UI", 10), muted=True
        ).pack(anchor="w", pady=(8, 24))

        btn = tk.Button(
            inner,
            text=button_text,
            command=lambda: webbrowser.open(url),
            bg=t["accent"], fg="#07111c",
            activebackground=t["accent"], activeforeground="#07111c",
            relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=18, pady=12,
        )
        btn.pack(anchor="w")
        return page


    def _build_guides_page(self):
        self.guides_page = self._build_link_page(
            "GUIDES",
            "Open your Star Citizen YouTube guides playlist.",
            "OPEN YOUTUBE GUIDES",
            GUIDES_URL,
        )

    def _build_announcements_page(self):
        self.announcements_page = self._build_link_page(
            "OFFICIAL ANNOUNCEMENTS",
            "Open the official Star Citizen Spectrum Announcements forum.",
            "OPEN RSI ANNOUNCEMENTS",
            ANNOUNCEMENTS_URL,
        )

    # -------------------- devices --------------------
    def refresh_devices(self):
        try:
            devices = sd.query_devices()
            choices = [
                ("Windows Default Recording Device", "__default__")
            ]

            for index, device in enumerate(devices):
                if int(device.get("max_input_channels", 0)) > 0:
                    choices.append((
                        f"{device.get('name', f'Input {index}')}  [Device {index}]",
                        index,
                    ))

            self.audio_devices = choices
            self.device_combo["values"] = [
                x[0] for x in choices
            ]

            if self.device_var.get() not in [
                x[0] for x in choices
            ]:
                self.device_var.set(
                    "Windows Default Recording Device"
                )
                self.selected_device = "__default__"

            self._device_selected()
        except Exception as exc:
            self.selected_device = None
            self.mic_label.configure(
                text="Microphone: unavailable"
            )
            self._history_add(
                f"Audio device error: {exc}",
                "error"
            )

    def _device_selected(self, *_):
        label = self.device_var.get()

        for item_label, token in self.audio_devices:
            if item_label == label:
                self.selected_device = token

                if token == "__default__":
                    try:
                        idx = int(sd.default.device[0])
                        info = sd.query_devices(idx, "input")
                        self.mic_label.configure(
                            text=f"Microphone: Windows default • {info.get('name', '')}"
                        )
                    except Exception:
                        self.mic_label.configure(
                            text="Microphone: Windows default"
                        )
                else:
                    self.mic_label.configure(
                        text=f"Microphone: {item_label}"
                    )
                break

    # -------------------- TTS voices / stop talking --------------------
    def _refresh_tts_voices(self):
        """Load installed Windows System.Speech voices."""
        try:
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=10,
            )
            voices = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
        except Exception:
            voices = []

        if not voices:
            voices = ["Windows Default Voice"]

        self.installed_voices = voices
        self.tts_voice_combo["values"] = voices

        saved = self.settings.get("tts_voice", "")
        if saved in voices:
            self.tts_voice_var.set(saved)
        else:
            # Prefer a commonly installed female Microsoft voice when present.
            female_candidates = [
                v for v in voices
                if any(name in v.lower() for name in ("zira", "aria", "jenny", "susan", "hazel"))
            ]
            self.tts_voice_var.set(
                female_candidates[0] if female_candidates else voices[0]
            )
        self._save_settings()

    def _stop_tts(self):
        """Immediately stop the current speech process."""
        with self.tts_lock:
            proc = self.tts_process
            self.tts_process = None

        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        proc.kill()
            except Exception:
                pass

    def _voice_stop_talking_match(self, heard):
        normalized = heard.lower().strip(" ,.!?-")
        return normalized in {
            "robot stop talking",
            "robot shut up",
            "robot stop speaking",
            "stop talking robot",
            "stop speaking robot",
        }

    # -------------------- status/history --------------------
    def _history_add(self, text, kind="info"):
        labels = {
            "info": "INFO",
            "heard": "HEARD",
            "match": "COMMAND",
            "error": "ERROR",
        }

        stamp = time.strftime("%H:%M:%S")

        self.history.configure(state="normal")
        self.history.insert(
            tk.END,
            f"[{stamp}]  {labels.get(kind,'INFO'):<8}  {text}\n"
        )
        self.history.see(tk.END)
        self.history.configure(state="disabled")

        current = int(
            self.command_count.cget("text").split()[0]
        )
        self.command_count.configure(
            text=f"{current + 1} events"
        )

    def _set_status(self):
        if self.running:
            self.status_label.configure(text="LISTENING")
            self.listen_button.configure(
                text="STOP LISTENING",
                bg=self.RED,
                fg="#ffffff",
                activebackground=self.RED,
                activeforeground="#ffffff",
            )
        else:
            accent_text = self._accent_text_color(self.theme["accent"])
            self.status_label.configure(text="OFFLINE")
            self.listen_button.configure(
                text="START LISTENING",
                bg=self.theme["accent"],
                fg=accent_text,
                activebackground=self.theme["accent"],
                activeforeground=accent_text,
            )

    def _set_voice_toggle_hotkey_status(self, text):
        if hasattr(self, "voice_toggle_hotkey_status"):
            self.voice_toggle_hotkey_status.configure(text=text)

    def _configure_voice_toggle_hotkey(self, keybind, show_error=True):
        """Register the optional global listen on/off key without hooks."""
        requested = str(keybind or "").strip().lower()

        if not requested:
            if self.voice_toggle_hotkey is not None:
                self.voice_toggle_hotkey.stop()
                self.voice_toggle_hotkey = None
            if hasattr(self, "voice_toggle_hotkey_var"):
                self.voice_toggle_hotkey_var.set("")
            self._set_voice_toggle_hotkey_status(
                "Leave blank to disable the keybind. Example: F8 or Ctrl+Shift+V."
            )
            self._save_settings()
            return True

        try:
            parse_global_hotkey(requested)
        except ValueError as exc:
            if show_error:
                messagebox.showerror("Voice Toggle Keybind", str(exc))
            self._set_voice_toggle_hotkey_status(f"Invalid keybind: {exc}")
            return False

        if (
            self.voice_toggle_hotkey is not None
            and self.voice_toggle_hotkey.keybind == requested
        ):
            self.voice_toggle_hotkey_var.set(requested)
            self._set_voice_toggle_hotkey_status(
                f"{requested.upper()} toggles listening on and off."
            )
            self._save_settings()
            return True

        old_hotkey = self.voice_toggle_hotkey
        if old_hotkey is not None:
            old_hotkey.stop()
            self.voice_toggle_hotkey = None

        try:
            listener = GlobalHotkey(
                requested,
                lambda: self.events.put(("voice_toggle_hotkey", requested)),
            )
            listener.start()
        except Exception as exc:
            message = (
                f'Could not register "{requested}". It may already be used by '
                "Windows, Star Citizen, or another app."
            )
            if show_error:
                messagebox.showerror("Voice Toggle Keybind", message)
            self._set_voice_toggle_hotkey_status(message)
            return False

        self.voice_toggle_hotkey = listener
        self.voice_toggle_hotkey_var.set(requested)
        self._set_voice_toggle_hotkey_status(
            f"{requested.upper()} toggles listening on and off."
        )
        self._save_settings()
        return True

    def _save_voice_toggle_hotkey(self):
        self._configure_voice_toggle_hotkey(
            self.voice_toggle_hotkey_var.get(),
            show_error=True,
        )

    def _clear_voice_toggle_hotkey(self):
        self._configure_voice_toggle_hotkey("", show_error=False)

    # -------------------- voice control --------------------
    def toggle_listening(self):
        if self.running:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        if self.running:
            return

        if self.selected_device is None:
            self.refresh_devices()

        if self.selected_device is None:
            messagebox.showerror(
                "Microphone Error",
                "No recording device is available."
            )
            return

        self.running = True
        self._set_status()
        self._history_add(
            "Voice control started. Commands are active immediately."
        )
        self._history_add(
            'Say "computer turn off" to fully stop listening.'
        )

        self.worker = threading.Thread(
            target=self._listen_loop,
            daemon=True,
        )
        self.worker.start()

    def stop_listening(self, reason="Voice control stopped."):
        self.running = False
        self._set_status()
        self._history_add(reason)

    def _speak(self, phrase="Command confirmed.", force=False):
        if not force and not self.voice_feedback_var.get():
            return

        def worker():
            # New speech interrupts old speech so answers do not pile up.
            self._stop_tts()

            try:
                safe_phrase = phrase.replace("'", "''")
                volume = max(0, min(100, int(self.tts_volume_var.get())))
                voice = self.tts_voice_var.get().strip()
                safe_voice = voice.replace("'", "''")

                voice_select = ""
                if voice and voice != "Windows Default Voice":
                    voice_select = (
                        f"try {{ $s.SelectVoice('{safe_voice}') }} catch {{ }}; "
                    )

                ps = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.Volume = {volume}; "
                    f"{voice_select}"
                    f"$s.Speak('{safe_phrase}')"
                )

                proc = subprocess.Popen(
                    [
                        "powershell", "-NoProfile",
                        "-WindowStyle", "Hidden",
                        "-Command", ps
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )

                with self.tts_lock:
                    self.tts_process = proc

                proc.wait()

                with self.tts_lock:
                    if self.tts_process is proc:
                        self.tts_process = None

            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()


    def _extract_keybind_question(self, heard):
        """
        Examples:
          what is k bound to
          what is i bound to
          what is f12 bound to
          what does f1 do
          what is right alt k bound to
        """
        text = heard.lower().strip()

        patterns = [
            r"what(?:'s| is) (.+?) bound to",
            r"what does (.+?) do",
            r"what(?:'s| is) the bind for (.+)",
        ]

        raw = None
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                raw = match.group(1).strip(" ?.,")
                break

        if not raw:
            return None

        aliases = {
            "spacebar": "space",
            "space bar": "space",
            "shift": "left shift",
            "control": "left control",
            "ctrl": "left control",
            "alt n": "left alt+n",
            "left alt n": "left alt+n",
            "right alt k": "right alt+k",
            "alt k": "right alt+k",
            "numpad eight": "numpad 8",
            "numpad two": "numpad 2",
            "numpad four": "numpad 4",
            "numpad six": "numpad 6",
            "numpad seven": "numpad 7",
            "numpad one": "numpad 1",
            "numpad five": "numpad 5",
        }
        raw = aliases.get(raw, raw)

        # Google may transcribe a single letter as "eye", "kay", etc.
        spoken_letters = {
            "eye": "i", "kay": "k", "bee": "b", "see": "c",
            "dee": "d", "gee": "g", "jay": "j", "queue": "q",
            "are": "r", "tea": "t", "you": "u", "why": "y",
            "ex": "x", "zed": "z", "zee": "z",
        }
        raw = spoken_letters.get(raw, raw)
        return raw

    def _keybind_answer(self, key):
        key = key.lower().strip()

        # First include any actions currently assigned to this key in the app.
        current = []
        for action_id, action in ACTIONS.items():
            bound = self.keybinds.get(action_id, action["key"]).lower()
            if bound == key:
                current.append(action["label"])

        reference = list(KEYBIND_REFERENCE.get(key, []))

        if current:
            app_part = "In this voice profile, " + ", ".join(current)
            if reference:
                return (
                    f"{key.upper()} is used for "
                    + "; ".join(reference)
                    + ". "
                    + app_part
                    + "."
                )
            return app_part + "."

        if reference:
            return (
                f"{key.upper()} is bound to "
                + "; ".join(reference)
                + "."
            )

        # Helpful special case for K.
        if key == "k":
            return (
                "K by itself is not in my current default reference. "
                "Right Alt plus K unlocks ship component ports."
            )

        return (
            f"I do not have a default Star Citizen binding for {key.upper()} "
            f"in my current reference."
        )

    def _extract_mining_location_question(self, heard):
        text = heard.lower().strip()
        patterns = [
            r"where can i mine (.+)",
            r"where do i mine (.+)",
            r"where is (.+) mined",
            r"where can i find (.+) for mining",
            r"where can i find (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                resource = match.group(1).strip(" ?.,")
                # Remove common filler words.
                resource = re.sub(r"\b(ore|resource|mineral)\b", "", resource).strip()
                if resource:
                    return resource
        return None

    def _build_phrase_matcher(self):
        pairs = []
        for action_id, phrases in self.phrases.items():
            for phrase in phrases:
                pairs.append((phrase, action_id))

        # Prefer longer / more specific phrases.
        pairs.sort(key=lambda x: len(x[0]), reverse=True)
        return pairs

    @staticmethod
    def _audio_level(raw_audio):
        """Return an RMS-like level for 16-bit microphone samples."""
        samples = memoryview(raw_audio).cast("h")
        if not samples:
            return 0
        mean_square = sum(sample * sample for sample in samples) // len(samples)
        return math.isqrt(mean_square)

    def _listen_loop(self):
        audio_q = queue.Queue(maxsize=300)

        def callback(indata, frames, time_info, status):
            if status:
                self.events.put((
                    "info",
                    f"Audio status: {status}",
                ))
            try:
                audio_q.put_nowait(bytes(indata))
            except queue.Full:
                # Recognition happens off the audio callback. Discarding stale
                # samples keeps a slow network result from adding extra lag.
                pass

        try:
            stream_device = (
                None
                if self.selected_device == "__default__"
                else self.selected_device
            )

            with sd.RawInputStream(
                samplerate=COMMAND_SAMPLE_RATE,
                blocksize=0,
                device=stream_device,
                channels=1,
                dtype="int16",
                callback=callback,
            ):
                self.events.put((
                    "info",
                    "Microphone active."
                ))

                while self.running:
                    chunks = []
                    preroll = collections.deque(
                        maxlen=COMMAND_PREROLL_CHUNKS
                    )
                    speech_started_at = None
                    last_voice_at = None

                    # Wait for actual speech, then finish soon after the user
                    # stops talking instead of always recording a fixed 4s.
                    while self.running:
                        try:
                            chunk = audio_q.get(timeout=0.10)
                        except queue.Empty:
                            continue

                        now = time.monotonic()
                        level = self._audio_level(chunk)

                        if speech_started_at is None:
                            preroll.append(chunk)
                            if level >= COMMAND_VOICE_THRESHOLD:
                                speech_started_at = now
                                last_voice_at = now
                                chunks = list(preroll)
                            continue

                        chunks.append(chunk)
                        if level >= COMMAND_VOICE_THRESHOLD:
                            last_voice_at = now

                        if (
                            now - last_voice_at
                            >= COMMAND_END_SILENCE_SECONDS
                        ):
                            break
                        if (
                            now - speech_started_at
                            >= COMMAND_MAX_CAPTURE_SECONDS
                        ):
                            break

                    if not self.running or not chunks:
                        continue

                    audio = sr.AudioData(
                        b"".join(chunks),
                        COMMAND_SAMPLE_RATE,
                        2,
                    )

                    # Do not process audio captured while the recognition API
                    # was responding; it would make the next command feel late.
                    while True:
                        try:
                            audio_q.get_nowait()
                        except queue.Empty:
                            break

                    try:
                        heard = self.recognizer.recognize_google(
                            audio
                        ).lower().strip()
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as exc:
                        self.events.put((
                            "error",
                            f"Speech API: {exc}",
                        ))
                        time.sleep(2)
                        continue

                    self.events.put(("heard", heard))
                    normalized = heard.strip(" ,.!?-")

                    # Stop current TTS without stopping voice recognition.
                    if self._voice_stop_talking_match(heard):
                        self._stop_tts()
                        self.events.put(("info", "TTS stopped by voice command."))
                        continue

                    # Hard voice-off.
                    if normalized in VOICE_OFF_PHRASES:
                        self._speak("Voice control off.", force=True)
                        self.events.put(("voice_off", ""))
                        break

                    # Reverse mining lookup takes priority over gameplay keybinds.
                    signature = self._extract_signature_question(heard)
                    if signature is not None:
                        answer = self._reverse_mining_tts_text(signature)
                        self._speak(answer, force=True)
                        self.events.put((
                            "mining_reverse",
                            f"{signature:,} → {answer}",
                        ))
                        continue

                    # Spoken keybind reference question.
                    asked_key = self._extract_keybind_question(heard)
                    if asked_key:
                        answer = self._keybind_answer(asked_key)
                        self._speak(answer, force=True)
                        self.events.put((
                            "keybind_query",
                            f"{asked_key} → {answer}",
                        ))
                        continue

                    # Mining location question.
                    mining_resource = self._extract_mining_location_question(heard)
                    if mining_resource:
                        threading.Thread(
                            target=self._mining_location_worker,
                            args=(mining_resource, True),
                            daemon=True,
                        ).start()
                        continue

                    # Gameplay commands.
                    now = time.time()
                    for phrase, action_id in self._build_phrase_matcher():
                        if phrase in heard:
                            if (
                                now - self.last_triggered.get(
                                    action_id, 0
                                )
                                < COOLDOWN_SECONDS
                            ):
                                continue

                            self.last_triggered[action_id] = now
                            action = ACTIONS[action_id]
                            bound_key = self.keybinds.get(action_id, action["key"])

                            try:
                                self._run_action(
                                    action["type"],
                                    bound_key,
                                    action["hold"],
                                )
                                suffix = (
                                    f"hold {action['hold']:.1f}s"
                                    if action["type"] == "hold"
                                    else "tap"
                                )
                                self.events.put((
                                    "match",
                                    f"{action['label']} ← “{phrase}” → {bound_key} [{suffix}]",
                                ))
                                self._speak(
                                    "Command confirmed."
                                )
                            except Exception as exc:
                                self.events.put((
                                    "error",
                                    f"Could not send '{bound_key}': {exc}",
                                ))

                            break

        except Exception as exc:
            self.events.put((
                "error",
                f"Listener stopped: {exc}",
            ))
        finally:
            self.events.put(("worker_done", ""))

    @staticmethod
    def _run_action(action_type, key, hold_seconds):
        if action_type == "tap":
            tap_keybind(key)
        elif action_type == "hold":
            hold_keybind(key, hold_seconds)
        elif action_type == "wheel":
            scroll_wheel(key)
        elif action_type == "combo_mouse":
            tap_mouse_combo(key)
        else:
            raise ValueError(action_type)

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()

                if kind == "heard":
                    self._history_add(
                        value, "heard"
                    )
                elif kind == "match":
                    self._history_add(
                        value, "match"
                    )
                elif kind == "error":
                    self._history_add(
                        value, "error"
                    )
                elif kind == "info":
                    self._history_add(
                        value, "info"
                    )
                elif kind == "mining_reverse":
                    self._history_add(
                        f"Mining lookup: {value}"
                    )
                elif kind == "keybind_query":
                    self._history_add(
                        f"Keybind answer: {value}"
                    )
                elif kind == "mining_locations":
                    resource, answer = value
                    self._history_add(
                        f"Mining locations: {answer}"
                    )
                    if hasattr(self, "mining_location_result"):
                        self.mining_location_result.configure(text=answer)
                elif kind == "ship_search_result":
                    self._set_ship_results(value)
                elif kind == "voice_off":
                    self.running = False
                    self._set_status()
                    self._history_add(
                        'Voice command "computer turn off" stopped listening.'
                    )
                elif kind == "voice_toggle_hotkey":
                    if (
                        hasattr(self, "voice_toggle_hotkey_var")
                        and value == self.voice_toggle_hotkey_var.get().strip().lower()
                    ):
                        self.toggle_listening()
                        self._history_add(
                            f"Listening toggled by keybind: {value.upper()}."
                        )
                elif kind == "worker_done":
                    if self.running:
                        self.running = False
                        self._set_status()

        except queue.Empty:
            pass

        self.after(50, self._drain_events)

    # -------------------- compact command catalog --------------------
    def _refresh_command_list(self, *_):
        if not hasattr(self, "command_list"):
            return

        self.command_list.delete(0, tk.END)
        category = self.category_var.get()

        for action_id, action in ACTIONS.items():
            if action["category"] != category:
                continue

            bound_key = self.keybinds.get(action_id, action["key"])
            display = (
                f"{action['label']:<28} → {bound_key}"
            )
            if action["type"] == "hold":
                display += f" ({action['hold']:.1f}s)"

            self.command_list.insert(
                tk.END,
                display,
            )

    def _test_selected(self, *_):
        selected = self.command_list.curselection()
        if not selected:
            return

        category = self.category_var.get()
        action_ids = [
            action_id
            for action_id, action in ACTIONS.items()
            if action["category"] == category
        ]
        action_id = action_ids[selected[0]]
        action = ACTIONS[action_id]
        bound_key = self.keybinds.get(action_id, action["key"])

        if not messagebox.askyesno(
            "Test Keybind",
            f"Send this keybind?\n\n"
            f"Action: {action['label']}\n"
            f"Key: {bound_key}\n"
            f"Type: {action['type']}"
            + (
                f"\nHold: {action['hold']:.1f}s"
                if action["hold"]
                else ""
            )
        ):
            return

        try:
            self._run_action(
                action["type"],
                bound_key,
                action["hold"],
            )
            self._history_add(
                f"Manual test: {action['label']} → {bound_key}",
                "match",
            )
            self._speak("Command confirmed.")
        except Exception as exc:
            messagebox.showerror(
                "Keybind Error",
                str(exc),
            )

    def on_close(self):
        self.running = False
        if self.voice_toggle_hotkey is not None:
            self.voice_toggle_hotkey.stop()
            self.voice_toggle_hotkey = None
        self._stop_tts()
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    VoiceKeybindApp().mainloop()
