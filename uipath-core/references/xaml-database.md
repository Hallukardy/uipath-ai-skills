# Database Activities

SQL database interaction via `UiPath.Database.Activities`. All activities live under the `ui:` namespace.

## Contents
- [When to use](#when-to-use)
- [Connection lifecycle](#connection-lifecycle)
- [DatabaseConnect](#databaseconnect)
- [DatabaseDisconnect](#databasedisconnect)
- [ExecuteQuery (SELECT → DataTable)](#executequery)
- [ExecuteNonQuery (INSERT/UPDATE/DELETE/DDL)](#executenonquery)
- [BulkInsert](#bulkinsert)
- [BulkUpdate](#bulkupdate)
- [InsertDataTable](#insertdatatable)
- [DatabaseTransaction](#databasetransaction)
- [Common pitfalls](#common-pitfalls)

## When to use

Reach for these activities when a PDD specifies a RDBMS source/sink (SQL Server, Oracle, PostgreSQL, MySQL, ODBC). For SharePoint lists, REST endpoints, or Orchestrator queues, use the relevant HTTP/Orchestrator activities instead.

**Prerequisite:** the robot machine must have the ADO.NET provider for the target database installed. Common providers:
- `Microsoft.Data.SqlClient` — SQL Server (modern; preferred over legacy `System.Data.SqlClient`)
- `System.Data.Odbc` — any ODBC-exposed source
- `Oracle.ManagedDataAccess.Client` — Oracle
- `Npgsql` — PostgreSQL (add via dependency manager)
- `MySql.Data.MySqlClient` — MySQL

## Connection lifecycle

Every database workflow should follow:
1. `DatabaseConnect` — open connection, store `DatabaseConnection` in a variable
2. `ExecuteQuery` / `ExecuteNonQuery` / `BulkInsert` / `BulkUpdate` / `InsertDataTable` / `DatabaseTransaction` — use the connection via `ExistingDbConnection` or `DatabaseConnection`
3. `DatabaseDisconnect` — close connection (put inside `Finally` block of an outer `TryCatch`)

Always wrap the entire block in `TryCatch` so `DatabaseDisconnect` runs even when a query fails.

## DatabaseConnect
→ **Use `gen_database_connect()`** — generates correct XAML deterministically.

Opens a connection and returns a `DatabaseConnection` object reused by downstream activities.

**Critical:** use `ConnectionSecureString` (SecureString input), not `ConnectionString`. The non-secure attribute exists but triggers lint warnings because it puts the password on the canvas.

Retrieve the connection string from Orchestrator Asset via `GetRobotCredential` / `GetRobotAsset`, never hardcode it in the workflow.

## DatabaseDisconnect

Self-closing. Takes a `DatabaseConnection` variable. Place in the `Finally` branch of a `TryCatch` so connections leak on failure are prevented.

## ExecuteQuery
→ **Use `gen_execute_query()`** — generates correct XAML deterministically.

Executes a parameterized `SELECT`, returns a `DataTable`.

**Always parameterize.** Pass values via the `Parameters` dictionary — never string-concatenate user input into the SQL. The helper emits the dictionary correctly; hand-authored SQL with inline values is a lint error (SQL injection).

Connection is passed via either `ExistingDbConnection` (from prior DatabaseConnect) or `ConnectionSecureString` (ad-hoc). The two are mutually exclusive — one must be `{x:Null}`.

## ExecuteNonQuery
→ **Use `gen_execute_non_query()`** — generates correct XAML deterministically.

Executes `INSERT`, `UPDATE`, `DELETE`, or DDL. Returns affected row count via `AffectedRecords`.

Same parameterization rule as ExecuteQuery. Same connection-exclusivity rule.

Use for single-row operations or schema changes. For many-row INSERT, prefer **BulkInsert** (orders of magnitude faster).

## BulkInsert

Insert the entire contents of a DataTable into a target table in a single round-trip. Requires the source DataTable's column names to match the target table's column names.

JSON spec:
```json
{
  "gen": "bulkinsert",
  "args": {
    "db_connection_variable": "dbConn",
    "table_name": "Customers",
    "data_table_variable": "dt_NewCustomers",
    "affected_records_variable": "intInserted"
  }
}
```

**Gotchas:**
- Target table must already exist (BulkInsert does not create it).
- Identity/auto-increment columns: leave them out of the source DataTable, or configure the provider to allow explicit inserts.
- NULLs: source DataTable cells must be `DBNull.Value`, not `""` or `null` — mismatched types cause provider-specific cast errors.

## BulkUpdate

Match rows in the DataTable to rows in the target table by key column(s) and update them. Best for "upsert"-style syncs where most rows are updates.

Shares the same shape as BulkInsert. Identity/auto-increment columns must map 1:1. Parameters: `db_connection_variable`, `table_name`, `data_table_variable`, `affected_records_variable` (output).

## InsertDataTable

Row-by-row insert (as opposed to BulkInsert's single round-trip). Slower but works with providers where BulkInsert is unavailable (e.g., older ODBC drivers). Prefer BulkInsert first; fall back to InsertDataTable only when the provider forces it.

Same parameters as BulkInsert.

## DatabaseTransaction

Executes its `Body` inside a single transaction. Any unhandled exception inside Body rolls back; normal completion commits. Nested queries inside the Body must use the same `DatabaseConnection` passed to the Transaction.

JSON spec:
```json
{
  "gen": "databasetransaction",
  "args": {
    "db_connection_variable": "dbConn",
    "use_transaction": "True"
  },
  "body": [
    { "gen": "execute_non_query", "args": { "..." } },
    { "gen": "bulkinsert", "args": { "..." } }
  ]
}
```

**⚠️ Generator emits an empty `<Sequence DisplayName="Do" />` placeholder body.** Caller must inject activities into the body — annotation-fallback does not yet wire child activities through the Body element. For complex transaction bodies, use `modify_framework.py` to inject or author a hand-written generator.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Hardcoded connection string | lint warning, security review fail | Use `GetRobotCredential` / `GetRobotAsset`; pass SecureString to `ConnectionSecureString` |
| Missing provider on robot | `Unable to find assembly …` at runtime | Add NuGet to project.json; ensure provider installed on robot machine; see `scripts/resolve_nuget.py` |
| Leaked connection | idle connections accumulate, eventual "connection pool exhausted" | Put `DatabaseDisconnect` in `Finally`, not after the last query |
| SQL injection via string concat | data leak / exception | Always use `Parameters` dictionary |
| Mixing `ExistingDbConnection` and `ConnectionSecureString` | Studio design error, activity refuses to run | Provide exactly one; set the other to `{x:Null}` |
| BulkInsert into non-existent table | runtime exception | Pre-create the table via `ExecuteNonQuery` DDL, or at project setup time |
| DataTable schema mismatch on BulkInsert | `String or binary data would be truncated`, `Invalid cast` | Define columns with exact target types; coerce values before populating |

## Template selection

None of these activities map to golden templates — the hand-written generators (`gen_database_connect`, `gen_execute_query`, `gen_execute_non_query`) and data-driven generators (`gen_bulkinsert`, `gen_bulkupdate`, `gen_insertdatatable`, `gen_databasedisconnect`, `gen_databasetransaction`) produce the XAML directly. Reference the harvested templates under `references/studio-ground-truth/UiPath.Database.Activities/2.0/` for Studio's default shape.
