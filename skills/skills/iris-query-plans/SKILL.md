---
name: iris-query-plans
description: Read an IRIS SQL query plan and fix index problems. Use when a query is slow, when a count or search returns fewer rows than the table holds, after adding an Index to a persistent class, or when iris_query(mode="explain") shows "Read master map" where you expected an index. Covers master map vs index map, Cost, %BuildIndices, INSERT %NOINDEX, WHERE %NOINDEX as a check, CREATE INDEX, TUNE TABLE and outlier selectivity.
author: tdyar
managed_by: iris-agentic-dev
---

# IRIS query plans and indexes

## Read the plan

`iris_query(mode="explain", query="SELECT ... WHERE ...")` returns the plan IRIS will run. Two lines matter most:

| Plan line                                                        | Meaning                                  |
| ---------------------------------------------------------------- | ---------------------------------------- |
| `Read master map Pkg.Table.IDKEY, looping on the subrange of ID` | full scan of the data rows               |
| `Read index map Pkg.Table.StatusIdx`                             | the query uses the index `StatusIdx`     |
| `Cost`                                                           | relative estimate; compare plans with it |

On a 5,000-row table, `WHERE Status = 'OPEN'` with no index costs 33000 and reads the master map. After `CREATE INDEX StatusIdx ON Pkg.Orders (Status)` the same query reads the index map at cost 13720.

## An index added in the class is empty until you build it

Adding `Index CustIdx On Customer;` to a persistent class and compiling it defines the index but does not fill it. Queries that the planner sends through the index then return short, with `SQLCODE = 0` and no error. On a table with 10 rows for customer `C1`:

```sql
SELECT COUNT(*) FROM Pkg.Orders WHERE Customer = 'C1'            -- 0
SELECT COUNT(*) FROM Pkg.Orders WHERE %NOINDEX Customer = 'C1'   -- 10
```

`%NOINDEX` in the WHERE clause tells the planner not to use an index for that condition, so it reads the data. When the two counts differ, the index is stale. Build it:

```objectscript
Set tSC = ##class(Pkg.Orders).%BuildIndices($ListBuild("CustIdx"))
If $$$ISERR(tSC) { Return tSC }
```

After the build, both counts are 10.

DDL is different. `CREATE INDEX` on a table that already has rows builds the index as part of the statement.

## `INSERT %NOINDEX` leaves the index behind

`INSERT %NOINDEX INTO Pkg.Orders ...` writes the row but skips index maintenance. A count through the index then misses the new row (0), and the same count with `WHERE %NOINDEX` finds it (1). So the method that does the `INSERT %NOINDEX` has to call `%BuildIndices` when its inserts are done:

```objectscript
For i = 1:1:tCount {
    Set tRs = tStmt.%Execute(...)
    If tRs.%SQLCODE < 0 { Return $$$ERROR($$$SQLError, tRs.%SQLCODE, tRs.%Message) }
}
Quit ##class(Pkg.Orders).%BuildIndices($ListBuild("CustIdx"))
```

A rebuild by hand lasts until the next load. If the loader clears the extent and inserts with `%NOINDEX` again, the index is empty again, and a fix that only ran `%BuildIndices` once is gone. Change the loader, or drop `%NOINDEX` from it.

## `TUNE TABLE`

`TUNE TABLE Pkg.Orders` gathers selectivity and extent size, and the planner uses them for later plans. On the test table the `CustIdx` plan stayed on the index map and its cost went from 3272 to 2672. Run it after a large load or when the data distribution changes.

## An outlier value reads the master map on purpose

If one value covers most of the rows, the planner skips the index for that value. With `Status = 'DONE'` on 98% of rows and `StatusIdx` present, the plan for `WHERE Status = 'DONE'` reads the master map at cost 33000, with the note "Using the outlier selectivity". That plan is correct. Reading nearly every row through an index costs more than a scan. A plan without the index is not always a missing index. Check which value the query uses before you add one.

## Checklist

1. Explain the query and read which map it uses.
2. If a count looks low, run it again with `WHERE %NOINDEX`. Different counts mean a stale index.
3. After adding an `Index` to a class that already has data, run `%BuildIndices`. A loader that uses `INSERT %NOINDEX` calls it itself, after its last insert.
4. After a large load, run `TUNE TABLE`.
5. A master-map plan for a common value is expected (outlier selectivity).

## Related skills

- `iris-sql`: SQL dialect, table naming, `SQLCODE`
- `objectscript-sql-patterns`: `%SQL.Statement` error checks
