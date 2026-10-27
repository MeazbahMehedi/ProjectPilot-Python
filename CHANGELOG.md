# Changelog

## 2.0.0 — 2026-10-27

- Rebuilt the original ProjectSelectionManager workflows around a sidebar desktop workspace.
- Added dark/light themes, live topic search, category filters, sortable tables, and favorites.
- Added student self-registration, individual credentials, salted PBKDF2 password hashing, and password changes.
- Added project descriptions, categories, statuses, deadlines, and validated capacities.
- Added atomic project switching: a failed switch keeps the student's previous assignment.
- Added FIFO waitlists with automatic assignment when a seat opens or capacity increases.
- Replaced manually decremented capacity with counts derived from current assignments.
- Added a role-scoped activity timeline, workspace JSON exports, formula-safe project CSV exports, and backups.
- Added a statistics dashboard, student assignment view, and keyboard shortcuts.
- Added launchers, source code, regression checks, screenshots, and detailed documentation.

## 1.0 — Provided Java project

- Java Swing UI with teacher/student menus.
- MySQL Projects and Students tables.
- Add/edit/delete topics, select/cancel projects, statistics, and CSV/JSON exports.
- External Gson and MySQL Connector dependencies.
