# Death Counter by MK

*Polska wersja: [README.md](README.md).*

A local Windows app that automatically counts deaths in games that show a distinctive message when you die, such as "YOU DIED" in the Dark Souls series, Elden Ring or Sekiro. The program recognizes that message in the game image using a template you calibrate once. It works offline and does not touch the game's files or memory.

## Download and run

1. Download the latest [`DeathCounter.exe`](https://github.com/Kacyn1/DeathCounter/releases/latest/download/DeathCounter.exe). The link always points to the newest version. Release notes and older versions are in [Releases](https://github.com/Kacyn1/DeathCounter/releases).
2. Put it in its own folder, e.g. `C:\Games\DeathCounter`. The program saves `config.json` and a `games` folder with each game's data (counter, bosses, calibration templates) next to itself.
3. Double-click to run. Python is not required.

The program has no digital signature, so Windows may show "Windows protected your PC". Click **More info → Run anyway**.

You can also run it from source: install [Python](https://www.python.org/downloads/) 3.12 or newer, download the repository (**Code → Download ZIP**) and double-click **`uruchom.bat`**. The first start creates a `.venv` and downloads the libraries (about 400 MB).

If the program folder is not writable, data goes to `%APPDATA%\DeathCounter`.

### Updates

Once a day the program asks GitHub whether a newer version exists. When one does, a "A new version is available" bar appears under the counter:
- **What's new** – opens the release notes;
- **Update** – downloads the new `DeathCounter.exe`, checks its SHA-256 checksum published by GitHub, replaces the program and restarts it. Your counters, bosses, calibration and certificates stay as they are. During a boss fight the program asks first and saves the fight time before restarting;
- **Later** – hides the bar until the next start.

Nothing is installed without clicking "Update". In the **About** window you can check for updates right away or turn off the daily check.

## Language

The program works in English or Polish. Change the language in the **About** window → **Language** list (PL / ENG) in the top-right corner. The choice is saved in `config.json` (`language`) and the program restarts in the new language. On the first start the language follows your Windows language.

The language applies to the whole interface, the PDF certificate and boss names. After a language change the program translates your saved boss names once to the names from the game's list in the new language (e.g. "Margit, Upadły Omen" → "Margit, the Fell Omen"), together with deaths, time and attempt history. Your game does not have to be in the same language as the program – name reading recognizes names in both languages.

## Choosing a game

The **Game** list above the counter: Dark Souls I, Dark Souls II, Dark Souls III, Sekiro: Shadows Die Twice, Elden Ring. Each game has its **own** death counter, bosses and calibration. Program settings (overlay, RTSS, thresholds, monitor) are shared.

Add a game that is not on the list with **+ Add game…** at the end of the list. The button next to the list moves the selected game's data to the **Recycle Bin** (after a Yes/No confirmation): **Delete counter** removes a game you added from the list, together with its counter, bosses and calibration. Built-in FromSoftware games cannot be removed – for them the button is **Reset counter**, which clears the death counter and boss list and keeps the calibration.

**Find installed Steam games…** on the list adds counters for souls-like games installed in Steam. The program reads the installed games from Steam's files on this computer (all libraries, no login or API key) and asks the Steam store for their tags – only the game numbers (AppID) are sent. Games with “Souls-like” among their 3 main tags, or on the built-in list of known souls-likes, are selected. Games with the tag in places 4–10 (usually games only inspired by Souls, e.g. Armored Core VI or Dead Cells) are listed separately as “possible souls-like” and are not selected. Without internet only the built-in list is used. Built-in games and games added before are skipped. An added game needs calibration like any other game that is not on the list. On the first start on a computer with Steam the program offers this search once.

## First use: calibration

1. Start the game (fullscreen or windowed).
2. Click **Calibration…** and get an image with the death message ("YOU DIED"). There are three ways:
   - while the death screen is visible, press **Ctrl+Alt+F9** (you will hear a beep), then open calibration;
   - set a delay and click **Capture screen**;
   - load a game screenshot (e.g. F12 in Steam).
3. Drag a rectangle around just the text and click **Check template**. The score should exceed the threshold.
4. Click **Save template**, then **Start**.

It is worth checking the template on a regular gameplay screenshot too – the score should be clearly lower than the threshold there.

## How detection works

- About every 0.1 s a frame is captured (DXCam). The area around the message is compared with the template (OpenCV, `TM_CCOEFF_NORMED`). The template scales automatically to the current resolution.
- **Confirmation:** a death counts only when the message is visible on 3 consecutive samples.
- **No duplicates:** after counting, the detector waits until the message has been gone for at least 3 s, and at least 8 s must pass between two deaths.
- **Image problems:** no new frames, a frozen image (over 5 s) and a resolution change are shown in the window. Nothing is counted meanwhile.

## Boss fights

With **"Track boss fights"** checked the program runs the fight by itself:

- boss health bar on screen → **Fight**: the timer runs, and the overlay shows the boss, its deaths and the total time;
- death message → **Death**: +1 to the overall counter and to the boss, the timer stops (walking back to the arena does not count);
- the bar is visible again → the fight with the same boss continues;
- victory message → **Boss defeated**: the timer stops for good.

**Save result** saves the final result with the DEFEATED status. **Discard** removes an entry created by mistake. If the bar disappears and neither a death nor a victory follows within 15 s, the program assumes you left the arena and marks the fight as abandoned.

**Results…** opens a table of all bosses in the selected game with their status, deaths and time. Double-click a boss to see its attempt history.

### Boss name reading

With **"Read the boss name from the screen"** on (the default), the program reads the name above the bar shortly after it appears. It uses the text recognition (OCR) built into Windows, with the English or Polish language pack – whichever is installed. It works offline and sends nothing anywhere.

- **Built-in name lists.** For Dark Souls I–III, Sekiro and Elden Ring (including DLC) the program has the boss names taken from the game files, in English–Polish pairs. A reading gets the most similar name from the selected game's list, in the program's language.
- **Boss name similarity** ("Detection" section, 0.60 by default) sets how much a reading may differ from a known name. Lower values correct more OCR errors, but a boss that is not on the list more easily gets someone else's name.
- **Fix boss names** in the "Results" window compares the saved names with the game's list, shows what it would change and replaces them after you confirm.
- The program learns names: a name you confirm or type by hand is remembered, and a misreading you corrected gives the right name next time.

### Boss fight calibration

**Calibration… → "Boss fight" tab** (or **Fight calibration…** in the panel) has two sub-tabs:

- **Boss bar** – an image from a fight. Select **the left end of the bar** (the decorative frame and the start of the bar), without the boss name and without the whole bar.
- **Victory message** – an image with the message shown after defeating a boss. Select just the text.

The victory message is visible only for a few seconds, so it is easiest to take F12 screenshots during the fight and at the moment of victory, and calibrate both templates later from files.

## Current session

The **Current session** section (below “Boss fight”) shows the deaths and time of the current play session. A session starts when you launch the game and its time runs only while the game is running – the program checks the list of Windows processes every 2 s (read-only, the game is not touched). The time runs only while the game is the active window: it pauses when you minimise the game, Alt+Tab to another window (also from borderless windowed mode), click another program or lock the screen. After you return to the game the program checks again about 2 s later whether it is still active, and then the time runs again with those 2 s counted. Returning to the game within 15 minutes (e.g. after a crash) continues the same session without counting the break; a longer break starts a new session. Each game has its own session, saved in `session.json` in the game folder, so restarting the program does not end it.

- **Track session** turns the feature on and off.
- **Switch the counter to the running game** – when you launch another game from the list, the counter switches to it and tells you so; if that game is not calibrated yet, the program reminds you and flashes on the taskbar. It happens only when a game starts, so choosing another game by hand while playing is not undone.
- **Show session on the overlay** adds the line “Session: 12 · 01:40:12” to the overlay and RTSS. The Discord status shows the time since the session started.
- **Session time and play time.** The session time is all the time the game is running and active, menus included. The play time leaves out the main menu and the loading after leaving it. It needs two templates from **Calibration… → Menu and gameplay** and detection turned on: **Main menu** (e.g. the game logo – while it is on screen the play time is paused) and **Character health bar** (its left end – after leaving the menu the play time starts only when the bar appears, so loading screens are not counted; afterwards the play time runs until you return to the menu, even if the bar is hidden). If the bar does not appear within 2 minutes, the gameplay starts anyway and that time is counted. Without these templates, or with detection off, the play time equals the session time. Deaths per hour in the statistics use the play time.
- **Session statistics…** opens a window (it does not block the program and refreshes every second) with two tabs: **Current session** – tiles and a line chart of total deaths over play time (each death is a step up, so steep parts show where you hit a wall); **All sessions** – tiles, a bar chart of deaths in each session (last 20) and a table of all sessions. Finished sessions are saved in `session_history.json` in the game folder; history and death times are recorded since version 1.12.0. The session state is shown as a badge: **IN GAME**, **MENU**, **LOADING**, **PAUSED**, **BREAK**, **WAITING**, **UNKNOWN GAME** or **OFF**.

Built-in games are recognised by their exe name, Steam games by their install folder, and games added by hand by the name of an installed Steam game. For a game outside Steam (e.g. GOG, Epic) the section shows **Choose game exe…**.

## PDF certificate

**PDF certificate…** saves a certificate for the selected game (A4 landscape): player name, game, total deaths, defeated bosses, deaths to bosses and the time it took to defeat them, plus the list of defeated bosses. It carries a verification code (an HMAC-SHA256 signature), signed data in the file metadata and an invisible watermark. If the score was changed by hand or outside the program, the certificate shows a red note and an "Adjustments" appendix. **Verify certificate…** checks whether a PDF is a genuine, unmodified certificate.

## Fullscreen games

- **Can you see the counter in the game?** **Show overlay / Hide overlay** turns the overlay on and off, and the **Overlay** row in the “State” section tells you whether the counter is visible: **VISIBLE**, **PARTLY** (window visible, but RTSS is not running – in fullscreen the counter may not be visible), **NOT VISIBLE** (“RTSS only” mode without RTSS running) or **HIDDEN** (overlay off), with a hint what to do.
- **Overlay through RTSS.** A regular "always on top" window often cannot appear over exclusive DirectX fullscreen, so the counter can be shown through [RivaTuner Statistics Server](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/). RTSS must be running with "Show On-Screen Display" turned on, and the mode must be "Window + RTSS" or "RTSS only". If RTSS is not installed, the program offers to install it through winget.
- **Global hotkeys** (defaults): **Ctrl+Alt+F9** – calibration screenshot, **Ctrl+Alt+F10** – +1, **Ctrl+Alt+F11** – −1, **Ctrl+Alt+F8** – overlay on/off. Change them with **Hotkeys…**.
- **Start detection on launch** lets you start the counter before the game without switching to its window.

## Discord status

**Discord status** (in the "Overlay" section) shows the selected game, the death count and the session time in your Discord status. The program only talks to the Discord app running on this computer.

## Reporting bugs: diagnostic file

A `diagnostyka.log` file is created next to the program (up to about 2 MB). It records the detection process: start and stop, every detected death, detector transitions, boss fight events and template match scores. It contains no images. When reporting a bug, attach this file and say what time the problem happened.

## License

Copyright (C) 2026 Mateusz Kacyna

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 3 ([GNU GPL v3](LICENSE), GPL-3.0-only), as published by the Free Software Foundation. It is distributed in the hope that it will be useful, but **without any warranty** – see the license text for details.

The program uses third-party libraries under their own licenses – Qt for Python (LGPL v3), OpenCV (Apache 2.0), NumPy (BSD), DXcam, comtypes and PyWinRT (MIT) and Python (PSF). The full texts are in [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) and in the **About** window.
