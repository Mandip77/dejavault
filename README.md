# 🔓 DejaVault (dejavault)

> **Unlock your memory to unlock your vault:** A cross-platform, 100% read-only SQLite forensics & "Context Time-Machine" CLI for recovering forgotten password clues on macOS, iOS backups, and desktop apps.

---

## 📖 Why This Project Exists (The Backstory)

I had an important locked Apple Note from **December 2021** that held personal information, and after five years, I completely forgot the password I used to lock it.

When I started investigating how Apple Notes stores data on macOS (`NoteStore.sqlite`), I discovered two major traps that lock people out of their own notes:

1. **The "Multiple Password Hints" Trap:** If you ever reset or change your Apple Notes password later on (for example, in 2024), Apple Notes updates your *account-level* password hint. However, **changing your Notes password never changes the password on old notes!** Your older notes remain encrypted with the original password from the day you locked them—and the original password hint is still sitting inside the raw SQLite database.
2. **Human Passwords Are Tied to Time & Context:** When we create a password or a hint (mine was simply `"person"`), we almost always use names, nicknames, dates, or phrases that were on our minds *that specific month*. By inspecting the database and looking at the unlocked notes I wrote around late 2021, I spotted the exact nicknames and names I was using back then—which immediately jogged my memory and unlocked the note.

I built **DejaVault** so anyone else who gets locked out of an old note or database can safely inspect their own metadata, uncover hidden historical password hints, and "time-travel" back to the exact era they locked their file—with zero risk to their live data.

---

## 🧠 How It Works (Explained Simply)

Think of your Notes app not as a folder of text files, but as a **digital vault spreadsheet** (`NoteStore.sqlite`).
* **What IS Encrypted:** The body of a locked note is encrypted using strong cryptography (`PBKDF2-SHA256` + `AES-GCM`).
* **What is NOT Encrypted:** So the app can display your sidebar and prompt you, the database leaves **Note Titles**, **Historical Password Hints**, **Creation/Modification Timestamps**, and **Neighboring Unlocked Notes** unencrypted.

When you run `dejavault`:
1. **Safe Sandbox Cloning:** It copies your target `.sqlite` database (plus its `-wal` and `-shm` write-ahead logs) into an isolated temporary folder and opens it in **strict read-only mode (`?mode=ro`)**, cleaning up automatically when finished.
2. **Legacy Lock vs. Account Reset Separation:** It separates your current account-level password hint from the original password hint attached to a specific older locked note.
3. **The Context Time-Machine (`±180 Days`):** It converts Apple CoreData timestamps (`+ 978307200s` offset from Jan 1, 2001), decompresses unlocked `zlib` protobuf note previews in memory, and highlights notes written around the same time (`⭐ ±Xd match`) while extracting proper nouns, names, dates, and PINs to jog your memory.
4. **Universal Cross-Platform Mode:** Works on **macOS**, **Windows**, and **Linux**—supporting macOS Apple Notes out of the box, extracted iOS/iPadOS backup databases (`4f98687d8ab0d6d1a371110e6b7300f6e465bef2`), and a **Universal SQLite Heuristic Scanner** for any other app (Bear, Joplin, Day One, etc.).

---

## 🚀 Quick Start (Beginner-Friendly)

### 1. Prerequisite on macOS: Grant Terminal "Full Disk Access"
By default, macOS sandboxing (**TCC**) blocks Terminal from copying `~/Library/Group Containers/group.com.apple.notes/` with an `Operation not permitted` error.
1. Open **System Settings** -> **Privacy & Security** -> **Full Disk Access**.
2. Toggle the switch **ON** next to **Terminal** (or iTerm2 / VS Code).
3. Quit (`Cmd + Q`) and reopen your terminal.

### 2. Install DejaVault
Requires Python 3.8+ and uses **zero third-party dependencies** (100% Python Standard Library).

    git clone [https://github.com/YOUR-USERNAME/dejavault.git](https://github.com/YOUR-USERNAME/dejavault.git)
    cd dejavault
    pip3 install -e . --break-system-packages 2>/dev/null || pip3 install -e .

### 3. Usage Examples

**Auto-Scan Apple Notes on macOS (With or Without a Clue):**

    dejavault
    dejavault --clue "person" --window 180

**Inspect an iPhone/iPad Backup on Windows, Linux, or macOS:**

    dejavault --db "/path/to/MobileSync/Backup/<UDID>/4f/4f98687d8ab0d6d1a371110e6b7300f6e465bef2"

**Scan Any Other App's SQLite Database (Universal Mode):**

    dejavault --db /path/to/any_app_database.sqlite --clue "2021" --universal

---

## 🛡️ Privacy & Security Guarantees
* **100% Offline & Local:** Zero network calls or external dependencies.
* **Read-Only Sandbox:** Never touches your live database directly; operates on a temporary clone opened with SQLite's `?mode=ro` URI flag and deletes the temp folder on exit.
* **Git-Safe:** Pre-configured `.gitignore` prevents `.sqlite`, `-wal`, and `-shm` files from ever being staged or committed.

## Development tests

Run the dependency-free tests from the repository root:

```sh
python -m unittest discover -s tests -v
```

The suite creates fictional in-memory or temporary SQLite databases and gzip
payloads. It does not require Apple Notes, a backup, or Full Disk Access.
The CI workflow runs the suite on Linux, macOS, and Windows with Python 3.9–3.12.
