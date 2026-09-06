# Kabutopz Voice Protocol

Kabutopz Voice Protocol is a Windows voice-command app for *Star Citizen*. It lets you run game actions with spoken phrases, edit keybinds, create custom commands, look up mining sites, and find current ship purchase and rental data.

The app uses Windows `SendInput` to send set keybinds. It does not use the third-party `keyboard` or `mouse` hook packages.

This is an accessibility tool.

## Features

- Voice commands for common *Star Citizen* actions
- Faster voice-activity capture that submits a command shortly after you stop speaking
- Optional global keybind to toggle listening on and off
- Editable phrases and keybinds with Ctrl, Alt, Shift, Left, and Right modifiers
- Custom commands with one or more trigger phrases
- UEX commodity price and buy/sell-location lookup
- Tap and Hold input modes
- Ship purchase and rental lookups
- Mining location questions with spoken answers
- Reverse mining-signature lookup
- Links to *Star Citizen* guides and announcements
- Saved settings and custom commands between launches

## Pages

The PAGE menu includes:

- **VOICE PROTOCOL** — Start and manage voice control.
- **HOW TO** — Learn the command, resource, and custom-phrase workflow.
- **COMMODITIES** — Search UEX commodity prices and buy/sell locations.
- **CUSTOMIZE** — Change app settings.
- **PHRASES** — Edit phrases and keybinds by group.
- **CUSTOM WORDS** — Create and manage custom voice commands.
- **KEYBINDS** — Search actions and change their keys.
- **MINING MODE** — Use mining tools and signature lookup.
- **SHIP FINDER** — Find ship purchase and rental details.
- **GUIDES** — Open the Kabutopz *Star Citizen* guides playlist on YouTube.
- **ANNOUNCEMENTS** — Open the official Spectrum Announcements forum.

## Voice Commands

While Voice Protocol is listening, speak a saved phrase to run its linked keybind.

For example:

```text
turn off star citizen
```

This command sends `Alt+F4`.

### Faster recognition

The microphone now waits for speech and submits the audio about 0.45 seconds
after you stop talking, instead of holding every command for a fixed four
seconds. Short commands should feel substantially faster. Internet speed and
Google's speech-recognition response time can still add a small delay.

Saying `computer turn off` confirms the command and adds, “Thank you for
flying with me.” Saying `thank you computer` (or `thanks computer`) receives a
random friendly reply.

### Listening toggle keybind

Under **VOICE PROTOCOL**, set an optional keybind under **VOICE ACTIVATION
TOGGLE KEYBIND**. It works globally, so it can turn listening on or off while
*Star Citizen* has focus.

Examples: `F8`, `Ctrl+Shift+V`, or `Alt+F10`.

It is blank by default. Leave it blank or use **CLEAR** to disable the toggle.
If Windows reports that a chosen key is already in use, choose another one.

## Custom Words

The **CUSTOM WORDS** page lets you:

- Name a new action.
- Pick an existing subcategory or enter a new one.
- Set a keybind, including Ctrl, Alt, Shift, and Left/Right modifier variants.
- Choose Tap or Hold.
- Add more than one trigger phrase.
- Turn each phrase on or off.
- Save the command for later use.

Saved custom commands join the normal voice matching list. They also appear in the **CUSTOM PHRASES** group on the **PHRASES** page.

To remove saved items, select a command under **EXISTING CUSTOM COMMANDS**, then use:

- **DELETE SELECTED PHRASE** to remove one phrase.
- **DELETE CUSTOM COMMAND** to remove the full command.

Each custom command must keep at least one phrase.

## Keybind Search

The **KEYBINDS** page can search by key, action, phrase, or category.

Use **FILTER BY KEYBIND** for an exact key match. For example, entering `K`, `I`, `F12`, or `alt+f4` shows only actions set to that keybind. This mode does not match action names or phrase text.

Use **SEARCH ALL** for a broad search, or **CLEAR** to reset the results.

## Ship Finder

Search for a ship by name, such as:

```text
Cutlass Black
```

The app checks the public Star Citizen Wiki community API and tries to show:

- Purchase locations
- Purchase prices
- Rental locations
- Rental prices

The app includes a Cutlass Black backup snapshot in case the live price format changes or the service cannot return data. Community data may change with each game patch.

## Mining Questions

While Voice Protocol is listening, ask a question such as:

```text
where can I mine iron
```

The app checks current Star Citizen Wiki commodity data and speaks the answer. If the live lookup fails, it uses a saved Iron hotspot list.

The existing reverse signature lookup remains on the **MINING MODE** page.

## Support

The header includes a Buy Me a Coffee link. Click the support text, button image, or box to open:

[buymeacoffee.com/kabutopz](https://buymeacoffee.com/kabutopz)

## Build

### Requirements

- Windows 10 or Windows 11
- Python 3 with `pip`
- The packages listed in `requirements.txt`
- An internet link for live ship and mining data

The app does not need the third-party `keyboard` or `mouse` hook packages. It sends game input through Windows `SendInput`.

The project uses these Python packages:

```text
SpeechRecognition>=3.10.4
sounddevice>=0.5.0
pyinstaller>=6.10
Pillow>=10.0
```

Save this list as `requirements.txt` in the project folder if that file is not already present.

### Install Dependencies

Open Command Prompt or PowerShell in the project folder. Create a virtual environment so the app's packages stay apart from your main Python setup:

```bat
py -m venv .venv
```

Start the virtual environment:

```bat
.venv\Scripts\activate
```

Update `pip`, then install the project packages:

```bat
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

This installs SpeechRecognition, sounddevice, Pillow, and PyInstaller. The build script uses PyInstaller to make the Windows app.

When you finish, you can leave the virtual environment with:

```bat
deactivate
```

### Create the App

Run this file from the project folder:

```bat
build_exe.bat
```

Run the build while the virtual environment is active so PyInstaller can include the right packages.

The build creates:

```text
dist\KabutopzVoiceProtocol\KabutopzVoiceProtocol.exe
```

Keep the full `KabutopzVoiceProtocol` folder together when you run or share the app. The build uses PyInstaller's one-folder mode, so the executable needs the other files in that folder.

The build also creates:

```text
dist\KabutopzVoiceProtocol\SHA256.txt
```

Use this file to check that the release files have not changed.

## Release Notes

The Windows build:

- Uses one-folder mode instead of a self-unpacking one-file build.
- Turns off UPX packing.
- Includes company, product, file, and version details.
- Bundles the app icons, logo art, and Buy Me a Coffee image.
- Creates a SHA-256 hash after each successful build.
- Avoids forced administrator elevation to reduce false-positive detection risk. If Star Citizen is running as Administrator, launch this app as Administrator manually so Windows can send keys to the game.

These steps can help cut false antivirus alerts, but no clean build can promise zero alerts from every antivirus tool. For public releases, sign each build with the same trusted code-signing certificate.

## Data Notice

Ship and commodity results come from the community-run Star Citizen Wiki API. The data may lag behind game updates, and fields may change without notice.

## Version

Kabutopz Voice Protocol v1.3
Powered by the Community <3

Future releases increment by 0.1: 1.0, 1.1, through 1.9, then 2.0.
