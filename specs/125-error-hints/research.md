# 125 research

## R1. SQLCODE -12 at `$`

From 123 research R1, reproduced again on 2026-09-23 through the CLI (`iris_query`, iris-dev-iris):

```text
INSERT INTO DemoB.Todo (Title, Completed) VALUES ($ZDATETIME($HOROLOG,3), 0)
  → SQL_ERROR: ERROR #5540: SQLCODE: -12 Message:  A term expected, beginning with either of:
    identifier, constant, aggregate, $$, (, :, +, -, %ALPHAUP, ... or %UPPER^ INSERT INTO DemoB .
    Todo ( Title , Completed ) VALUES ( $
SELECT $ZDATETIME($HOROLOG,3) FROM DemoB.Todo
  → SQL_ERROR: ... or %UPPER^ SELECT $
```

The list of expected terms itself contains `$$` and `^`, so the match reads the text after the
last `^` and checks it ends with a single `$`.

## R2. System classes outside %SYS

2026-09-23, `iris-agentic-dev tool iris_execute` against iris-dev-iris (community 2026.2):

| Code                                                  | USER                                               | %SYS                |
| ----------------------------------------------------- | -------------------------------------------------- | ------------------- |
| `##class(Security.Applications).Exists("/csp/sys")`   | `<CLASS DOES NOT EXIST> ... Security.Applications` | `1`                 |
| `##class(Config.Namespaces).Exists("USER")`           | `<CLASS DOES NOT EXIST> ... Config.Namespaces`     | `1`                 |
| `##class(SYS.Database).%ClassName(1)`                 | `<CLASS DOES NOT EXIST> ... SYS.Database`          | `SYS.Database`      |
| `##class(Security.Users).%New()`                      | `<CLASS DOES NOT EXIST> ... Security.Users`        | `23@Security.Users` |
| `##class(Security.Roles).Get("x",.p)`                 | `<CLASS DOES NOT EXIST> ... Security.Roles`        | (empty)             |
| `$classmethod("Security.Applications","Exists","/x")` | `<CLASS DOES NOT EXIST> ... Security.Applications` | `0`                 |
| `##class(%SYS.ProcessQuery).%ClassName(1)`            | `%SYS.ProcessQuery`                                | same                |
| `##class(%SYSTEM.Security).%ClassName(1)`             | `%SYSTEM.Security`                                 | same                |
| `##class(Nope.Missing).Foo()`                         | `<CLASS DOES NOT EXIST> ... Nope.Missing`          | same                |

The class name is the last token of the error line. `%` packages resolve everywhere, and a class
that does not exist fails in both, so neither gets a hint.
