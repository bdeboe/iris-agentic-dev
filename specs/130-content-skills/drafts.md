# 130 issue drafts (not filed)

Bugs in iad itself that the 130 probes found. None is fixed in 130. Each is written as a GitHub issue body, and none has been filed. The reproductions are in `research.md`.

## 1. `iris_test` package pattern returns NO_TESTS_FOUND and blames the name

`iris_test(pattern="IadProbe130")` returns `NO_TESTS_FOUND` although `IadProbe130.Misnamed` is a compiled `%UnitTest.TestCase` with a passing `TestOk`. The hint says to use a bare package name with no wildcard, which is what I passed. `iris_test(pattern=":IadProbe130.Misnamed")` finds and runs it.

What I expected: either the package form runs the package's test classes, or the hint says the working form is `:Package.Class`. Under the hood, `RunTest("IadProbe130")` wants a directory `^UnitTestRoot/IadProbe130/` and runs nothing without it, so the package form may never be able to work over Atelier. Then the hint is the fix.

Side effect: `^UnitTestRoot` on iris-dev-iris is now `/tmp/`. I did not record its old value.

## 2. `&sql(INSERT ...)` in a `For` loop fails in `iris_execute`

Embedded `&sql(INSERT INTO ...)` inside a `For` loop, run through `iris_execute`, fails with `<UNDEFINED> sqlSQLCODE1`. The same insert outside the loop works. My guess is the generated wrapper method and the loop's embedded-SQL variables, but I have not checked the generated INT.

## 3. `iris_macro expand` returns `{}` for a defined macro

**Fixed locally in 130 round 3; not filed.** Every action called a route Atelier does not have (`/action/getmacro` answers 404, `/docnames/INC` 400). The handler now uses `getmacrolocation`/`getmacrodefinition`/`getmacroexpansion`/`getmacrosignature` and `/docnames/RTN/INC`. It finds the defining include when none is named, and it returns `MACRO_NOT_FOUND` rather than `{}`. The body below is the report as found.

`iris_macro(action="expand", name="eProductionStateRunning")` returns `result: {}`. `EnsConstants.inc` defines it as 1. The call should return the expansion, or an error naming the include it searched.

This is what failed SKILL-16 in the 130 round-2 ladder, in both arms. Agents asked `iris_macro` for `eProductionStateRunning` (`definition` and `expand`, in BENCHMARK and ENSLIB) and got `{}` or `null`. `action="list"` said "No include files found in this namespace". `iris_search(category="INC")` found nothing. The agents then guessed the value as 2 and wrote `If state = 2 { Quit $$$OK }` for "already running". Stopped is 2, so the check fails. A `success: true` with an empty result reads as "exists, value empty". An error such as "macro not found in any include this namespace can see" would at least stop the guess.

## 4. `iris_doc put` hides `result.status` errors

For a one-line XML class export put under its `.cls` name, Atelier answers `result.status: ERROR #16021: Illegal Header Line`, with `status.errors` empty, and stores nothing. `iris_doc(mode="put", compile=true)` reports the put as fine, and the agent's only error is `#5351: Class ... does not exist` from the compile after it. So the agent never learns that the put failed or why. `iris_doc put` should fail on a non-empty `result.status`, and show the text.

## 5. `iad exec` prints nothing when the CODE_EDIT gate refuses

`iad exec 'Set tSC=$system.OBJ.DeletePackage("X","-d")'` exits 1 with nothing on stdout or stderr. The same code through `iad tool iris_execute` returns `CODE_EDIT_BLOCKED` with the matched text, the reason and the remediation (use `iris_doc`). The CLI drops all of it. Someone scripting `exec` sees a bare failure and nothing to act on. `exec` should print the refusal message and the remediation on stderr.

## 6. `iris_doc` with a class name and no `.cls` returns a raw #16006

`iris_doc(mode="get", name="Bench.Calc.Math", category="CLS")` returns `BAD_REQUEST` with `ERROR #16006: Document 'Bench.Calc.Math' name is invalid`. The class exists, and `name="Bench.Calc.Math.cls"` works. `category` only filters `mode="list"`, so it does not supply the extension. The error does not say the extension is missing.

In the 130 round-2 ladder (SKILL-14, skill arm, run 0), the agent made this call 10 times across `get`, `fragment`, `head` and `put`. It concluded the classes were "protected from edits" by a mapping and stopped. The tools arm on the same task used `.cls` and passed.

What I expected: when a `get`/`head`/`fragment`/`put` name has no document extension and matches a class, either add `.cls` or return an error that says "document names need an extension: `Bench.Calc.Math.cls`".

## 7. `iris_info what=sa_schema` is described as "SQL Analytics schema"

It calls Atelier `/saschema/<url>`, the Studio Assist grammar for an XData namespace, not a BI cube or SQL schema. On iris-dev-iris, `v6/USER/saschema/http://www.intersystems.com/deepsee` returns the `deepsee:` element grammar (6.7 KB), and `saschema/HoleFoods` returns 404 with an empty result. The tool description reads "what=sa_schema returns SQL Analytics schema", and PR 142's `iris-mdx` skill took it at its word: its discovery workflow calls `iris_info(what=sa_schema, name=<CubeName>)` to list cubes and spec paths. The description should say "Studio Assist schema for an XData namespace URL (`name` is the URL)". BI cube discovery goes through `iris_execute` with `%DeepSee.Utils:%GetCubeList` and `%GetDimensionList`.
