# Contract: ladder CLI and task additions

## `python -m tests.e2e.skill_eval.ladder`

| Flag         | Values               | Default                           | Effect                                                                                                                      |
| ------------ | -------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `--side`     | `holdout` \| `train` | `holdout`                         | Picks which split side runs, and writes `side` into every run record. `train` records are refused by `assert_holdout_only`. |
| `--web-port` | int                  | env `IRIS_WEB_PORT`, then `52780` | Passed to `IsolatedEnv.with_mcp(iris_web_port=…)` and to the check CLI's env.                                               |

Existing flags do not change. `--task` still filters within the chosen side, and an id on the other side prints `no <side> task matches …` and exits 2.

## Task YAML `teardown`

```yaml
teardown: |
  <ObjectScript; runs in `namespace`; may switch to %SYS with New $NAMESPACE>
```

- It runs once before the session and once after the check.
- A non-zero CLI exit makes the run unscored (`CheckBroken`), with a reason naming the task and `teardown`.
- If the field is absent, behaviour is unchanged.

## `python -m tests.e2e.skill_eval.tool_calls list <run_id>`

- Reads `tests/e2e/results/<run_id>.transcripts/*`.
- Output is one block per session, headed `== <task> <arm> repeat=<n> ==`, then one line per tool call:

  ```text
  <n>\t<tool>\t<ok|err>\t<first 120 chars of the result, newlines as ⏎>
  ```

- Exit 0. If `run_id` has no transcripts dir, it exits 2 naming the path.
