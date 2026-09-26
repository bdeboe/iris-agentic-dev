# 129 research: live reproductions and mined counts

Every capture below came from `iris-dev-iris` (IRIS Community 2026.2) through iad's own tools on 2026-09-26, in `USER` unless marked. Setup classes: `Test129.Hint` (property `Title`) and `Test129.Sub.Deep` (property `Name`), compiled with `cuk` and left in `USER`. Their sources are in `tests/e2e/tasks/hints/setup/`.

## R1. The spec 125 SQL rule names the wrong function

The -12 hint said "an ObjectScript function such as $ZDATETIME or $HOROLOG". In IRIS SQL, `SELECT $HOROLOG`, `$PIECE(...)`and`$LENGTH(...)` all succeed. `$ZDATETIME`and`$ZDATE` fail with -12 at `$`:

- `INSERT INTO Test129.Hint (Title) VALUES ($ZDATETIME($HOROLOG,3))`, write mode → -12, marker at `... VALUES ( $`.
- `SELECT TOP 1 $ZDATE(1) AS d FROM Test129.Hint` → -12, marker at `SELECT TOP ? $`.

Decision: the text says "such as $ZDATETIME" and drops `$HOROLOG`.

## R2. %SYS-only tables (rule `sys_only_table`)

| Query (USER)                                   | Error                                         |
| ---------------------------------------------- | --------------------------------------------- |
| `SELECT TOP 1 Name FROM Security.Users`        | -30 `Table 'SECURITY.USERS' not found`        |
| `SELECT TOP 1 Name FROM Security.Roles`        | -30 `Table 'SECURITY.ROLES' not found`        |
| `SELECT TOP 1 Name FROM Security.Applications` | -30 `Table 'SECURITY.APPLICATIONS' not found` |
| count mode, `Config.Namespaces`                | -30 `Table 'CONFIG.NAMESPACES' not found`     |

All four succeed in `%SYS`. `Security.NoSuch` in `%SYS` gives -30 (negative: the table is missing).

`SYS.` is excluded. `SYS.Database` gives -30 in `USER` and in `%SYS`: it is a class, not a table. The SYS schema has 3 tables (for example `SYS.BackgroundIntegrity`), against 36 in Config and 18 in Security, so a `SYS.` -30 is more often a class name than a %SYS table.

## R3. Three-level class names cut to two (rule `deep_package_table`)

| Query                                     | Error or result                          |
| ----------------------------------------- | ---------------------------------------- |
| `SELECT TOP 1 Name FROM Test129.Sub.Deep` | -30 `Table 'SUB.DEEP' not found`         |
| count mode, table `Test129.Sub.Deep`      | -30 `Table 'SUB.DEEP' not found`         |
| `SELECT TOP 1 Name FROM Test129_Sub.Deep` | success                                  |
| `SELECT TOP 1 Name FROM Nope.Sub.Deep`    | -30 `Table 'SUB.DEEP' not found`         |
| `%Dictionary.Class.Definition`            | -30 `Table 'CLASS.DEFINITION' not found` |

IRIS drops the first segment and reports the last two. The rule fires when the reported name equals the last two segments of an `A.B.C` token in the query, and suggests `A_B.C`. `Nope.Sub.Deep` fires too; the suggestion `Nope_Sub.Deep` is still the right spelling, and a second -30 on it says the class is missing.

## R4. Double quotes around a string (rule `double_quoted_string`)

- `SELECT Title FROM Test129.Hint WHERE Title = "hello"` → -29 `Field 'HELLO' not found in the applicable tables^ SELECT Title FROM Test129 . Hint WHERE Title = "hello"`.
- `Super = "%Persistent"` against `%Dictionary.ClassDefinition` → -29 `Field '%PERSISTENT' not found`.
- `WHERE Name %STARTSWITH "Test"` → -29 `Field 'TEST' not found`.
- Single quotes succeed. `SELECT "Title" FROM Test129.Hint` succeeds (a quoted identifier is fine).
- Negative: `SELECT TOP 1 Nope FROM Test129.Hint` → -29 `Field 'NOPE'`, no quotes in the query, no hint.

## R5. Reserved words as aliases (rule `reserved_word`)

`AS FOUND`, `AS Level`, `AS count`, `AS Module`, `AS User` each give -1 `IDENTIFIER expected, reserved word LEVEL found^ ...` (with the word in upper case). The quoted forms `AS "Level"`, `AS "count"` and `AS "User"` succeed. `AS Value` succeeds (not reserved).

## R6. SQLite and MySQL INSERT forms (rule `nonstandard_insert`)

| Statement (write mode)                                                 | Error                                                                |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `INSERT OR IGNORE INTO Test129.Hint (Title) VALUES ('a')`              | -1 `UPDATE expected, IDENTIFIER (IGNORE) found^ INSERT OR IGNORE`    |
| `INSERT OR REPLACE INTO Test129.Hint (Title) VALUES ('a')`             | -1 `UPDATE expected, IDENTIFIER (REPLACE) found^ INSERT OR REPLACE`  |
| `INSERT IGNORE INTO Test129.Hint (Title) VALUES ('a')`                 | -30 `Table 'SQLUSER.IGNORE' not found`                               |
| `INSERT INTO Test129.Hint (Title) VALUES ('a') ON CONFLICT DO NOTHING` | -25 `Input (ON) encountered after end of query^ ... VALUES ( ? ) ON` |

## R7. Error shapes the matchers must read

- EXPLAIN wraps the inner error: `SQLCODE: -482 Message: EXPLAIN error: SQLCODE = -30 :  Table ...`. The matchers take the last `SQLCODE: -N` or `SQLCODE = -N`.
- Write-mode errors have the same text as read mode.
- `iris_query mode=explain` accepts SELECT only.

## R8. Checked and left without a rule

- `SELECT FROM Test129.Hint` → -12 at `SELECT FROM`. Not ObjectScript, no rule.
- `WRITE 1` sent to `iris_query` → -51 `An SQL statement expected, WRITE found`. No skill section covers it.
- `SET x = 1` → -1 `OPTION expected`.
- `for i=1:1:3 { quit 5 }` and a top-level `quit 5` → `<COMMAND>`, but `while 1 { quit 5 }` succeeds. The difference is unexplained, so no rule.
- `write x` → `<UNDEFINED>`. Too generic for a hint.

## R9. Mined errors

I scanned Tom's Claude Code session logs (`~/.claude/projects/*/*.jsonl`) for `iris_query` results with `error_code: SQL_ERROR`: 60 unique (query, error) pairs, plus 148 SQLCODE -30 lines in free text across all logs. What recurs:

- -30 on a %SYS table: `SECURITY.USERS` (4), `SECURITY.AUDIT`, `CONFIG.NAMESPACES`.
- -30 on a cut name: `CLASS.DEFINITION` (4), `SUB.DEEP`.
- -1 reserved word: `MODULE` (8+), `FOUND` (8), `ROWS` (2), `PROCEDURE`.
- -30 `SQLUSER.IGNORE`.
- -12 on `$ASCII`/`$LENGTH` mixed with other functions, and on `$SYSTEM.` calls.
- -29 on unquoted field names that do not exist (real typos or wrong table, no rule).

Most of the 60 come from projects whose queries name customer tables. Only error text that names system tables or reserved words goes into the fixture; queries from those projects are not copied.
