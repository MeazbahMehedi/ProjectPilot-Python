# Original Java project and migration

The source was Java Swing/MySQL ProjectSelectionManager. Python rewrites the workflows in Tkinter/SQLite; Java retains Swing and uses local JSON persistence. Neither new edition executes the old program or needs the MySQL connector.

| Original responsibility | Current responsibility |
| --- | --- |
| MainInterface / launcher | Current role-specific desktop navigation |
| AuthHandler | Individual credentials, role checks, account administration |
| TeacherHandler | Owned topics, applications, milestones, submissions and reports |
| StudentHandler | Direct selection, applications, teams, progress and submissions |
| DBHelper | Current storage, migration and integrity rules |
| DataExporter | Scoped CSV/JSON and printable PDF reports |

| Original field | New meaning |
| --- | --- |
| project_id | Mapped internal project ID |
| project_name | title |
| supervisor_name | supervisor display name |
| remaining_team_members | Remaining seats; add selected student count to obtain total capacity |
| student_id | Student account ID, preserved as text |
| student_name / major | Account name / major |
| selected_project_id | Mapped student assignment |

3.0.1 includes a paired CSV importer for original Projects/Students exports. See [import-templates/README.md](import-templates/README.md). It does not run the old SQL, connect to MySQL or use the old destructive DROP TABLE statement. The original embedded database password was removed.

Same-edition 2.0 workspaces migrate automatically, preserving a pre-upgrade backup. Existing topics remain Direct and initially belong to teacher. Admins can create supervisors and transfer ownership.

ProjectPilot and TopicNest share the same rewrite and features. Their names, accent colors, Python package names, Java executable names and maintainer displays differ.
