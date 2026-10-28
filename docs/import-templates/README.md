# CSV templates and legacy migration

Use **Import & reports** in the app. Preview validates the CSV and hides passwords. Save the preview only after reviewing it.

## Project import

`projects.csv` uses total capacity. Title and capacity are required. Omitted supervisor defaults to the current account's name, category to Imported, description to Imported project, deadline to 30 days from import, status to Open and mode to Approval. Ownership is the signed-in supervisor/admin. Transfer ownership later using admin project editing.

## Student import (admin)

`students.csv` includes ID, name and major. Supply the fallback initial password in the dialog; you can optionally include a `password` column with per-student values. Passwords need 8–128 characters. Do not commit real credential CSVs. Existing or repeated account IDs cause the import to fail rather than overwrite accounts.

## Legacy paired migration (admin)

Export both original MySQL tables through your database client, with headers and UTF-8 encoding. Preserve IDs as text, including leading zeros. Use `legacy-projects.csv` and `legacy-students.csv` as the expected shapes. Do not use the generic project importer for legacy remaining-seat counts.

Choose **Legacy paired migration**, set an initial student password and a selection deadline, then select the Projects CSV followed by the Students CSV. Inspect the preview and confirm. Total capacity is legacy remaining seats plus the number of students selecting that project. Unknown project references, duplicate IDs or existing student account conflicts reject the migration.

Migration creates new internal project IDs and maps old selections to them. It creates Direct topics owned by the signed-in administrator. Transfer them to supervisor accounts after import. It does not change or connect to the old MySQL database. Reset/imported passwords must be shared with the intended students outside this local app; email delivery is not included.
