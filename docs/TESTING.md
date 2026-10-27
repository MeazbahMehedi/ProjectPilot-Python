# Verification record

Product: ProjectPilot-Python 2.0.0  
Date: 2026-10-27  
Environment: Linux; Python 3.12 / OpenJDK 17; virtual X11 display for GUI checks.

## Completed checks

| Check | Result |
| --- | --- |
| Business-rule regression suite | PASS — 18 unittest cases, including a real two-thread last-seat race |
| Login and logout screens | PASS |
| Supervisor Overview, Projects, Students, Activity, Settings | PASS |
| Student Overview, Projects, My selection, Activity, Settings | PASS |
| Live project search | PASS |
| Dark and light themes | PASS |
| Minimum supported window layout | PASS |
| Real launch entry point with a new temporary workspace | PASS |
| Six running-UI screenshots | Captured and embedded in README |

Tests use temporary workspaces and do not ship test databases. Persistence uses SQLite transactions and foreign keys. The two named distributions share the same business rules, with separate branding and maintainer display.

## Practical limits of verification

These checks were run on Linux. Windows batch launchers were reviewed but were not executed on Windows. The Python and Java applications use native GUI libraries, so fonts and control rendering can differ by operating system. Automated page checks do not click every possible native file-picker path. Exports and backups are covered directly at the service layer. No remote-server, multi-device, encryption, or disaster-recovery guarantees are claimed.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 -m tests.ui_smoke
```
