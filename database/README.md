## Download Full Databases

The full database files are provided in GitHub Releases.

Download `SemQueryBench_database_full.zip` from the latest release and extract it under the repository root:

```powershell
Expand-Archive -Path SemQueryBench_database_full.zip -DestinationPath .
```

After extraction, the directory should be:
```text
database/full/[db_name]/[table_name].csv
```

CSV files are used only as a portable release format. During evaluation, all tables are loaded into MySQL using database/load_to_mysql.py.