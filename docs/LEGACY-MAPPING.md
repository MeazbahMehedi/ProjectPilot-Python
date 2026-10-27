# Original project and migration notes

The uploaded source was a Java Swing/MySQL application named **ProjectSelectionManager**. Version 2.0 rewrites its workflows; it does not wrap or execute the old Java program.

| Original source | Responsibility in version 2.0 |
| --- | --- |
| `ProjectSelectionManager.java` / `MainInterface.java` | Launcher and desktop navigation |
| `AuthHandler.java` | Account registration, login, password changes, role checks |
| `StudentHandler.java` | Student selection, cancellation, waitlisting and saved topics |
| `TeacherHandler.java` | Supervisor topic management and assignment reports |
| `DBHelper.java` | Storage initialization, integrity rules and reporting |
| `DataExporter.java` | Role-scoped JSON and project CSV exports |

The Python edition implements these responsibilities with Python/Tkinter and SQLite. The Java edition keeps Java/Swing and uses an atomic JSON store with the supplied Gson 2.11.0 dependency. No MySQL service or connector is needed for either new edition.

## Legacy field mapping

| Legacy MySQL field | New field / meaning |
| --- | --- |
| `Projects.project_id` | Project `id` |
| `Projects.project_name` | Project `title` |
| `Projects.supervisor_name` | Project `supervisor` |
| `Projects.remaining_team_members` | Remaining seats; **not** the new total capacity |
| `Students.student_id` | Student account `id` |
| `Students.student_name` | Student account `name` |
| `Students.major` | Student account `major` |
| `Students.selected_project_id` | Student assignment to a project |

When transferring existing records, total capacity must equal legacy remaining seats **plus** the number of selected students. New description, category, status, deadline and account credentials also need to be supplied.

**Existing MySQL records are not automatically imported.** The uploaded SQL contains two example projects and two example students, not a running database snapshot. Version 2.0 initializes a separate fictional demo workspace. Keep the old database intact. For a small real dataset, create accounts and projects in the new app, set total capacities correctly, then let students select their projects. A bulk migration requires a dedicated importer; none is included.

The original database password and hardcoded login checks were removed. The original SQL's destructive `DROP TABLE Students` statement is not used by the new apps. Demo credentials are documented openly and should be changed before entering real records.

## What is shared between the named distributions?

ProjectPilot and TopicNest use the same application rules and equivalent features. Branding, accent color, package name (Python), executable name (Java), and maintainer display differ. They are named distributions of the same rewrite, not independently developed projects. The README retains the original Java history in both distributions.
