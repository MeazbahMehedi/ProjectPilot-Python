# ProjectPilot-Python 3.0.1 verification

Verified on 2026-10-27 with Linux, Python 3.12/OpenJDK 17 and a virtual X11 display for native GUI checks.

| Check | Result |
| --- | --- |
| Service regression suite | PASS — 45 unittest cases |
| Admin / supervisor / student page navigation | PASS |
| Supervisor ownership and student record scope | PASS |
| Individual/team approval and whole-group capacity rejection | PASS |
| Revision requests, resubmission and pending-application restrictions | PASS |
| Milestone status, attachments, submission feedback and notifications | PASS |
| CSV preview, quoted fields and transaction rollback | PASS |
| Paired legacy migration with correct total capacity and preserved IDs | PASS |
| Same-edition 2.0 workspace migration | PASS |
| Preferences, themes, topic search and modal project details | PASS |
| Inline validation and clean form cancellation | PASS |
| Actual asynchronous CSV import through the desktop UI | PASS |
| Project table at minimum window size | PASS |
| Real main.py / executable-JAR launch using a new temporary data directory | PASS |
| Printable PDF syntax, pagination and visual layout | PASS |
| Current screenshots | 14 running-UI captures with fictional demonstration data |

Tests and screenshots use temporary workspaces. The supplied files contain no real student databases, test accounts beyond source-defined demo defaults, or copied submission directories.

## Platform limits

Windows batch files, PowerShell builders, GitHub Actions YAML and Inno Setup recipes were prepared and reviewed as source. They were not executed on Windows here, and no prebuilt Windows EXE is included. Native fonts/dialogs can vary by operating system. The installer workflow needs a Windows runner with its build dependencies. Standard PDF fonts have the Western/Latin character coverage described in README; CSV/JSON preserve Unicode.

These checks do not claim a hosted service, email delivery, cross-device synchronization, encryption, exhaustive native file-picker testing or universal recovery from filesystem/power failures. The Java store is local JSON with a process lock, while Python uses SQLite transactions.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 -m tests.ui_smoke
python3 -m tests.ui_smoke --out docs/screenshots
```
