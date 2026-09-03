# Kabutopz Voice Protocol v7.1

This build adds permanent Kabutopz branding to the Command History area, renames the application/window to Kabutopz Voice Protocol, and builds as `KabutopzVoiceProtocol.exe`.

## New pages

The PAGE dropdown now includes:

- VOICE PROTOCOL
- CUSTOMIZE
- PHRASES
- KEYBINDS
- MINING MODE
- SHIP FINDER
- GUIDES
- ANNOUNCEMENTS

## SHIP FINDER

Search for a ship such as:

`Cutlass Black`

The app queries the public Star Citizen Wiki community API for current vehicle data and tries to display:

- Purchase locations
- Purchase prices
- Rental locations
- Rental prices

A Cutlass Black fallback snapshot is included if the live price schema changes or is temporarily unavailable.

The live data is community-maintained and patch-sensitive.

## Mining location questions

While Voice Protocol is listening, ask:

`where can I mine iron`

The app queries the current Star Citizen Wiki commodity data and answers with TTS.

If live lookup fails, the Iron fallback hotspot list includes places such as:

- Pyro V-c (Adir)
- Pyro V-b (Vatra)
- Pyro III (Bloom)
- Magda
- Lyria
- Calliope
- Pyro I
- Pyro II (Monox)
- microTech
- Wala
- Yela Asteroid Belt
- Aaron Halo

The existing reverse signature lookup remains in MINING MODE.

## KEYBINDS page

A new searchable keybind editor lets you filter by:

- Key
- Action
- Phrase
- Category

Select an action and directly change its keybind.

The PHRASES page remains available for grouped phrase + keybind editing.


## GUIDES

Opens the user's YouTube Star Citizen guides playlist.

## ANNOUNCEMENTS

Opens the official Star Citizen Spectrum Announcements forum.

## Build

Run:

`build_exe.bat`

Output:

`dist\KabutopzVoiceProtocol\KabutopzVoiceProtocol.exe`

Keep the complete `KabutopzVoiceProtocol` output folder together. The app is
intentionally built in one-folder mode rather than as a self-extracting
one-file executable.

## Antivirus false-positive reduction

- Removed the third-party `keyboard` and `mouse` hook packages.
- Sends configured gameplay inputs through Windows `SendInput` only.
- Uses PyInstaller one-folder mode instead of a self-extracting one-file overlay.
- Disables UPX compression.
- Adds Windows company, product, filename, and version metadata.
- Generates `SHA256.txt` beside the executable after every successful build.
- For public distribution, sign every release with the same trusted code-signing identity. A clean build alone cannot guarantee that every antivirus vendor will return zero detections.

## v7.1 Branding Update

- Windows EXE/taskbar/window icon uses the full Kabutopz logo.
- Full Kabutopz logo appears on the far left of the header.
- Love Kabutops graphic appears beside the title.
- Subtitle is `VERSION 7.1 • POWERED BY CHAT`.

## v7.1 Header Revision

- Left header graphic changed to Salute Kabutopz.
- Love Kabutops remains beside the title.
- RADIO page removed.

## v7.1 Custom Words + Alt-F4 Update

- Added `Turn Off Star Citizen` with phrase `turn off star citizen` → `Alt+F4`.
- Added a new **CUSTOM WORDS** page.
- Custom Words lets you:
  - Create an action name.
  - Pick an existing subcategory or type a new one.
  - Assign a keybind.
  - Choose Tap or Hold.
  - Add multiple phrase rows.
  - Check/uncheck which phrases are active.
  - Save the command permanently.
- Custom actions are merged into normal voice matching and persist between launches.
- KEYBINDS search now has exact-key mode:
  - typing `K` only shows actions bound to `K`
  - typing `I` only shows actions bound to `I`
  - typing `F12` only shows actions bound to `F12`
  - typing `alt+f4` only shows actions bound to `Alt+F4`

## Buy Me a Coffee support link

- Added a boxed Buy Me a Coffee button immediately left of the PAGE selector.
- The box displays `Support is appreciated!` above the button image.
- Clicking the text, PNG button, or surrounding box opens `https://buymeacoffee.com/kabutopz` in the default browser.
- The PNG is bundled into the standalone EXE.


## v7.1 Custom Words Manager + Key Filter

### Custom Words deletion
Select one of your saved custom commands under **EXISTING CUSTOM COMMANDS**.

- **DELETE SELECTED PHRASE** removes one saved trigger phrase.
- **DELETE CUSTOM COMMAND** removes the entire custom command.
- A custom command must keep at least one phrase.

### Strict KEYBINDS filter
The KEYBINDS page now has:
- **FILTER BY KEYBIND**
- **SEARCH ALL**
- **CLEAR**

Type `K`, `I`, `F12`, `alt+f4`, etc. and press **FILTER BY KEYBIND**. Only actions whose actual assigned keybind exactly matches the typed key are shown. Phrase text and action names are ignored in this mode.

### CUSTOM PHRASES group
The PHRASES page now includes **CUSTOM PHRASES** in the GROUP dropdown. Every command created on the CUSTOM WORDS page appears there automatically.
