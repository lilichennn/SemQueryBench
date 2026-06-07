# Database Files

The full database files of SemQueryBench are released separately through GitHub Releases due to file size.

## Structure

Each database is stored as a directory, and each table is stored as a CSV file.

After downloading and extracting the full database package, the directory should be:

```text
database/full/
├── [db_name]/
│   ├── [table_name].csv
│   └── ...

Each subdirectory corresponds to one database, and each CSV file corresponds to one table.

## Download

Download SemQueryBench_database_full.zip from the latest GitHub Release and extract it under the repository root.

## For PowerShell:

```PowerShell
Expand-Archive -Path SemQueryBench_database_full.zip -DestinationPath .
```
After extraction, the full database files should be located under:

```text
database/full/
```

## Load into MySQL
The CSV files are used only as a portable release format. During evaluation, all tables should be loaded into MySQL and SQL predictions should be executed against the reconstructed relational databases.
```
python database/load_to_mysql.py --database_root database/full
Sample Databases
```
The database/sample/ directory provides small sample databases for checking the expected file format. These files are not the full benchmark databases.