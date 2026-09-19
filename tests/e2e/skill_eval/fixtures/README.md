# Fixtures

Captured harness output, kept so a driver's parsing can be tested without paying for a session.

## `prime_agent_session.jsonl`

One real `prime-agent 0.8.1` headless run, captured 2026-09-18 for spec 120 T006:

```bash
PATH=/opt/homebrew/opt/node@22/bin:$PATH TMPDIR=$(mktemp -d) HOME=<sandbox> \
  prime-agent --mode json --no-session --provider openai --model gpt-4.1 \
  -p 'Call the iris-agentic-dev MCP tool iris_info once and report the IRIS version. Do nothing else.'
```

The session made two `ipython` calls — `await mcp.list_tools("iris-agentic-dev")` and
`await mcp.call_tool("iris-agentic-dev", "iris_info", {"what": "metadata"})` — and reported the
version off the second. Cost $0.0624, 46,323 tokens, most of it the 81-tool listing landing in
context.

Two edits to the 142-event stream, and nothing else:

- The 128 `message_update` deltas are dropped. They repeat the message they are building, and no
  driver reads them.
- Strings over 400 characters end in `…[truncated for fixture]`, and `agent_end`'s 137 KB replay of
  the whole conversation is a placeholder. The 81-tool `list_tools` result is the only payload this
  actually touches.

So the shapes are real and the field names are real; the long text is not. Assert on structure here,
never on a truncated string's tail.
