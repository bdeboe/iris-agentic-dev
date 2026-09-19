"""Unit tests for per-tool attribution — 121 T039, written before `attribution.py`.

Story 5 is a join, not a run: the sessions already recorded which tools they called, and joining that
log to each task's graded result answers "which of the 81 tools earn their place" for free.

Three things the join has to get right, and all three are ways of being honest about a zero:

- **Every advertised tool appears, reached or not** (FR-012). A table of the tools that were used is a
  table with no bad news in it.
- **Zero reach has two meanings, and they are different findings.** No corpus task could have used the
  tool — that is a gap in the corpus. A task could have and the agent reached for something else —
  that is a gap in the tool's description, which is the thing this program exists to fix.
- **Reach rate is over applicable tasks, not all tasks.** `iris_mirror_status` reaching 0 of 41 tasks
  is meaningless when none of the 41 is about mirroring; 0 of 0 is the honest denominator.

Applicability is declared, not inferred from the result. `tool_applicability.toml` maps each tool to
one domain and each task tag to the domains it touches, and it is committed before the join runs, for
the same reason the split is committed before the figure: a denominator chosen after seeing the
numerator is not a denominator.
"""

import pytest

from tests.e2e.skill_eval.pilot import ArmRun

# A three-tool, two-domain table. Small on purpose: the committed table is checked against the real
# advertised surface in its own test below, and everything else here is about the arithmetic.
TABLE = {
    "tools": {
        "iris_doc": "objectscript-code",
        "iris_query": "sql",
        "iris_mirror_status": "mirroring",
    },
    "tags": {"sql": "sql", "mirror": "mirroring"},
    "baseline": ["objectscript-code"],
}


class FakeTask:
    def __init__(self, task_id, tags=()):
        self.id = task_id
        self.tags = tuple(tags)


def call(name, *, server="iris_agentic_dev", completed=True, status=None, error=None):
    return {
        "name": name,
        "server": server,
        "completed": completed,
        "status": status or ("completed" if completed else "error"),
        "error": error,
    }


def run(task_id, arm="tools", passed=True, calls=()):
    return ArmRun(
        task_id=task_id,
        arm=arm,
        passed=passed,
        tool_calls=len(calls),
        calls=tuple(calls),
    )


# --- applicability, declared before the join -------------------------------------------------------


def test_a_task_touches_the_baseline_domains_and_the_ones_its_tags_name():
    from tests.e2e.skill_eval import attribution

    assert attribution.task_domains(FakeTask("CORPUS-01"), table=TABLE) == {
        "objectscript-code"
    }
    assert attribution.task_domains(FakeTask("CORPUS-02", ["sql"]), table=TABLE) == {
        "objectscript-code",
        "sql",
    }


def test_applicable_tasks_are_the_ones_whose_domains_include_the_tools():
    from tests.e2e.skill_eval import attribution

    tasks = [FakeTask("CORPUS-01"), FakeTask("CORPUS-02", ["sql"])]
    assert attribution.applicable_tasks("iris_query", tasks, table=TABLE) == (
        "CORPUS-02",
    )
    assert attribution.applicable_tasks("iris_doc", tasks, table=TABLE) == (
        "CORPUS-01",
        "CORPUS-02",
    )
    assert attribution.applicable_tasks("iris_mirror_status", tasks, table=TABLE) == ()


def test_a_tool_the_table_does_not_classify_raises_rather_than_scoring_zero():
    """A tool added to the surface and not to the table would otherwise appear as unreached with an
    applicable count of zero — which reads as "no task needed it" and is really "nobody said"."""
    from tests.e2e.skill_eval import attribution

    with pytest.raises(attribution.Unclassified) as caught:
        attribution.applicable_tasks(
            "iris_brand_new", [FakeTask("CORPUS-01")], table=TABLE
        )
    assert "iris_brand_new" in str(caught.value)


# --- the join --------------------------------------------------------------------------------------


def test_every_advertised_tool_appears_including_the_unreached_ones():
    from tests.e2e.skill_eval import attribution

    rows = attribution.attribute(
        runs=[run("CORPUS-01", calls=[call("iris_doc")])],
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_doc", "iris_query", "iris_mirror_status"],
        table=TABLE,
    )
    assert [row["tool"] for row in rows] == [
        "iris_doc",
        "iris_query",
        "iris_mirror_status",
    ]


def test_zero_reach_with_no_applicable_task_says_no_task_needed_it():
    from tests.e2e.skill_eval import attribution

    (row,) = attribution.attribute(
        runs=[run("CORPUS-01", calls=[call("iris_doc")])],
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_mirror_status"],
        table=TABLE,
    )
    assert row["verdict"] == "no task needed it"
    assert row["applicable_tasks"] == 0
    assert row["reach_rate"] is None, "0 of 0 is not 0%"


def test_zero_reach_with_applicable_tasks_says_the_agent_chose_otherwise():
    """The finding this whole table exists for: the task was in the tool's domain, the tool was
    advertised, and the agent solved it some other way. That is a description problem."""
    from tests.e2e.skill_eval import attribution

    (row,) = attribution.attribute(
        runs=[run("CORPUS-02", calls=[call("iris_doc")])],
        tasks=[FakeTask("CORPUS-02", ["sql"])],
        surface=["iris_query"],
        table=TABLE,
    )
    assert row["verdict"] == "a task needed it and the agent chose otherwise"
    assert (row["applicable_tasks"], row["reached_tasks"]) == (1, 0)
    assert row["reach_rate"] == pytest.approx(0.0)


def test_reach_rate_is_over_applicable_tasks_not_every_task():
    from tests.e2e.skill_eval import attribution

    tasks = [
        FakeTask(f"CORPUS-{i:02d}", ["sql"] if i <= 2 else []) for i in range(1, 5)
    ]
    (row,) = attribution.attribute(
        runs=[run("CORPUS-01", calls=[call("iris_query")])],
        tasks=tasks,
        surface=["iris_query"],
        table=TABLE,
    )
    # One of the two sql tasks reached it. Over all four it would read 25%, which describes the corpus
    # rather than the tool.
    assert row["reach_rate"] == pytest.approx(0.5)


def test_a_builtin_call_is_not_a_reach_for_the_iad_tool_of_the_same_name():
    """`bash` is a tool call and is not part of the surface under measurement. A call the harness
    served counts for nothing here, whatever it was named."""
    from tests.e2e.skill_eval import attribution

    (row,) = attribution.attribute(
        runs=[run("CORPUS-01", calls=[call("iris_doc", server=None)])],
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_doc"],
        table=TABLE,
    )
    assert row["reached_tasks"] == 0


def test_the_bare_arm_does_not_count_against_reach():
    """The bare arm has no tools by construction, so counting its tasks in the denominator would
    report the arms' design as the tools' failure."""
    from tests.e2e.skill_eval import attribution

    runs = [
        run("CORPUS-01", arm="bare", passed=False, calls=[]),
        run("CORPUS-01", arm="tools", calls=[call("iris_doc")]),
    ]
    (row,) = attribution.attribute(
        runs=runs, tasks=[FakeTask("CORPUS-01")], surface=["iris_doc"], table=TABLE
    )
    assert row["reached_tasks"] == 1
    assert row["sessions_with_tools"] == 1


# --- failure modes ---------------------------------------------------------------------------------


def test_the_errors_a_tool_returned_are_reported_verbatim_and_counted():
    """Goal 3's failure mode. Four reaches all erroring the same way is one bug; four different
    errors is four. The text is what a reader can act on, so it is not summarized into a rate."""
    from tests.e2e.skill_eval import attribution

    runs = [
        run(
            "CORPUS-01",
            calls=[
                call("iris_execute", completed=False, error="CODE_EDIT_BLOCKED"),
                call("iris_execute", completed=False, error="CODE_EDIT_BLOCKED"),
                call("iris_execute"),
            ],
        )
    ]
    (row,) = attribution.attribute(
        runs=runs,
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_execute"],
        table={
            **TABLE,
            "tools": {**TABLE["tools"], "iris_execute": "objectscript-code"},
        },
    )
    assert (row["calls"], row["failed_calls"]) == (3, 2)
    assert row["failure_modes"] == {"CODE_EDIT_BLOCKED": 2}


def test_a_call_that_failed_with_no_message_is_counted_under_its_status():
    from tests.e2e.skill_eval import attribution

    runs = [
        run(
            "CORPUS-01",
            calls=[call("iris_doc", completed=False, status="pending", error=None)],
        )
    ]
    (row,) = attribution.attribute(
        runs=runs, tasks=[FakeTask("CORPUS-01")], surface=["iris_doc"], table=TABLE
    )
    assert row["failure_modes"] == {"pending (no message)": 1}


# --- did the tasks that used it do better? ---------------------------------------------------------


def test_the_pass_rate_of_tasks_that_called_it_is_reported_beside_those_that_did_not():
    """Not a lift and not labelled as one. Which tasks called a tool is the agent's choice, so this is
    an observational split — reported because it is the only per-tool signal a single corpus run can
    give, and named as what it is."""
    from tests.e2e.skill_eval import attribution

    tasks = [FakeTask(f"CORPUS-{i:02d}", ["sql"]) for i in range(1, 5)]
    runs = [
        run("CORPUS-01", passed=True, calls=[call("iris_query")]),
        run("CORPUS-02", passed=False, calls=[call("iris_query")]),
        run("CORPUS-03", passed=True, calls=[call("iris_doc")]),
        run("CORPUS-04", passed=False, calls=[call("iris_doc")]),
    ]
    (row,) = attribution.attribute(
        runs=runs, tasks=tasks, surface=["iris_query"], table=TABLE
    )
    assert row["pass_rate_when_called"] == pytest.approx(0.5)
    assert row["pass_rate_when_not_called"] == pytest.approx(0.5)
    assert row["observational"] is True


def test_an_unscored_run_contributes_reach_but_not_a_pass_rate():
    """A session the harness could not grade still shows which tools the agent reached for. What it
    cannot do is vote on whether they worked — spec 118's rule, one level down."""
    from tests.e2e.skill_eval import attribution

    runs = [run("CORPUS-01", passed=None, calls=[call("iris_doc")])]
    (row,) = attribution.attribute(
        runs=runs, tasks=[FakeTask("CORPUS-01")], surface=["iris_doc"], table=TABLE
    )
    assert row["reached_tasks"] == 1
    assert row["pass_rate_when_called"] is None


# --- the committed table, against the real advertised surface --------------------------------------


def test_the_committed_table_classifies_every_tool_the_binary_advertises():
    """The one test that reads the real surface. A tool added to the router and not to the table is a
    row that would read "no task needed it" while nobody had decided anything."""
    from tests.e2e.skill_eval import attribution, provenance

    binary = provenance.resolve_binary()
    if not binary:
        pytest.skip("no iris-agentic-dev binary resolved; set IAD_BINARY")
    tools = provenance.tool_list(binary)
    assert tools, "the binary would not list its tools, so the surface is unknown"
    table = attribution.load_table()
    missing = sorted(
        tool["name"] for tool in tools if tool["name"] not in table["tools"]
    )
    assert not missing, (
        f"tool_applicability.toml does not classify {', '.join(missing)} — add each to a domain "
        "before the next run, or the table reports them as tools no task needed"
    )


def test_every_domain_the_table_names_for_a_tag_is_a_domain_some_tool_serves():
    """A tag pointing at a domain no tool has is a denominator that can never be reached, and it would
    inflate nothing visibly — it just sits there looking like coverage."""
    from tests.e2e.skill_eval import attribution

    table = attribution.load_table()
    served = set(table["tools"].values())
    named = set(table["tags"].values()) | set(table["baseline"])
    assert named <= served, f"no tool serves {sorted(named - served)}"


def test_every_tag_in_the_corpus_is_either_mapped_or_deliberately_baseline_only():
    """An unmapped tag is not an error — most tags are topical (`loops`, `precedence`) and add no
    domain. What must not happen is a tag being silently misspelled into invisibility, so the corpus's
    own tags are checked against the table and the unmapped ones are listed in the report."""
    from tests.e2e.skill_eval import attribution, graded_task

    tags = {tag for task in graded_task.all_tasks() for tag in task.tags}
    table = attribution.load_table()
    unknown = sorted(tag for tag in table["tags"] if tag not in tags)
    assert not unknown, (
        f"the table maps {', '.join(unknown)}, which no task carries — a mapping for a tag that does "
        "not exist is a denominator that never fires"
    )


# --- the skills rung's own domain ------------------------------------------------------------------


class FakeSkillTask:
    def __init__(self, task_id, skill):
        self.id = task_id
        self.tags = ()
        self.skill = skill


def test_a_task_that_names_a_skill_makes_the_skill_tools_applicable():
    """The per-skill rung's whole premise is that the document is reachable, and `skill_search` and
    `skill` are how an agent reaches it. A skills task where no skill tool was touched is the finding
    Goal 2 needs beside its counts."""
    from tests.e2e.skill_eval import attribution

    table = {**TABLE, "tools": {**TABLE["tools"], "skill_search": "skills"}}
    tasks = [FakeSkillTask("SKILL-01", "iris-sql"), FakeTask("CORPUS-01")]
    assert attribution.applicable_tasks("skill_search", tasks, table=table) == (
        "SKILL-01",
    )


# --- the rendered table — T041 ---------------------------------------------------------------------


def rows_for_render():
    from tests.e2e.skill_eval import attribution

    tasks = [FakeTask("CORPUS-01"), FakeTask("CORPUS-02", ["sql"])]
    runs = [
        run("CORPUS-01", calls=[call("iris_doc")]),
        run(
            "CORPUS-02",
            calls=[call("iris_doc", completed=False, error="UNKNOWN_PARAMETER: mode")],
        ),
    ]
    return attribution.attribute(
        runs=runs, tasks=tasks, surface=list(TABLE["tools"]), table=TABLE
    )


def test_the_table_puts_the_passed_over_tools_first():
    """81 rows sorted by name buries the finding. The tools an applicable task could have used and
    nobody reached for are the reason the table exists, so they are at the top."""
    from tests.e2e.skill_eval import attribution

    rendered = attribution.format_table(rows_for_render())
    body = [line for line in rendered.splitlines()[2:]]
    assert "iris_query" in body[0], rendered
    assert "iris_doc" in body[1]
    assert "iris_mirror_status" in body[2]


def test_a_tool_with_no_applicable_task_prints_a_dash_not_a_zero_percent():
    from tests.e2e.skill_eval import attribution

    rendered = attribution.format_table(rows_for_render())
    mirror = [line for line in rendered.splitlines() if "iris_mirror_status" in line][0]
    assert "| — |" in mirror and "0%" not in mirror


def test_the_failure_table_names_the_message_and_the_tool_that_returned_it():
    from tests.e2e.skill_eval import attribution

    rendered = attribution.format_failure_modes(rows_for_render())
    assert "iris_doc" in rendered
    assert "1x UNKNOWN_PARAMETER: mode" in rendered


def test_a_run_with_no_failed_call_says_so_rather_than_printing_an_empty_table():
    from tests.e2e.skill_eval import attribution

    rows = attribution.attribute(
        runs=[run("CORPUS-01", calls=[call("iris_doc")])],
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_doc"],
        table=TABLE,
    )
    assert attribution.format_failure_modes(rows) == "No tool call failed in this run."


def test_unreached_lists_only_the_tools_worth_acting_on():
    from tests.e2e.skill_eval import attribution

    names = [row["tool"] for row in attribution.unreached(rows_for_render())]
    assert names == ["iris_query"]


# --- reading a written report ----------------------------------------------------------------------


def a_report():
    """The shape `ladder.report` writes: runs as dicts, not `ArmRun`s."""
    return {
        "provenance": {"run_id": "ladder-20260918T000000", "tool_surface": "1.4.2+abc"},
        "arms": ["bare", "tools"],
        "runs": [
            {
                "task_id": "CORPUS-01",
                "arm": "tools",
                "passed": True,
                "reason": None,
                "timed_out": False,
                "tool_calls": 1,
                "seconds": 30.0,
                "session_seconds": 20.0,
                "run_index": 0,
                "calls": [call("iris_doc")],
            },
            {
                "task_id": "CORPUS-01",
                "arm": "bare",
                "passed": False,
                "reason": None,
                "timed_out": False,
                "tool_calls": 0,
                "seconds": 30.0,
                "session_seconds": 20.0,
                "run_index": 0,
                "calls": [],
            },
        ],
    }


def test_the_runs_in_a_written_report_join_without_being_rebuilt_as_arm_runs():
    """The artifact on disk is the input. Requiring `ArmRun` here would mean the only way to attribute
    a run is to still have the Python objects from four hours ago."""
    from tests.e2e.skill_eval import attribution

    rows = attribution.attribute(
        runs=attribution.runs_from_report(a_report()),
        tasks=[FakeTask("CORPUS-01")],
        surface=["iris_doc"],
        table=TABLE,
    )
    assert rows[0]["reached_tasks"] == 1
    assert rows[0]["pass_rate_when_called"] == pytest.approx(1.0)


def test_the_rendered_document_names_the_run_it_came_from():
    """A standing table with no run id behind it is a table nobody can re-derive."""
    from tests.e2e.skill_eval import attribution

    rows = attribution.attribute(
        runs=attribution.runs_from_report(a_report()),
        tasks=[FakeTask("CORPUS-01")],
        surface=list(TABLE["tools"]),
        table=TABLE,
    )
    text = attribution.render_document(a_report(), rows)
    assert "ladder-20260918T000000" in text
    assert "1.4.2+abc" in text
    assert "| `iris_doc` |" in text
    assert "observational" in text.lower()


def test_the_document_names_the_passed_over_tools_in_prose_not_only_in_the_table():
    """FR-012 again: a reader who skims must still see which tools nobody reached for."""
    from tests.e2e.skill_eval import attribution

    rows = attribution.attribute(
        runs=attribution.runs_from_report(a_report()),
        tasks=[FakeTask("CORPUS-01", ["sql"])],
        surface=list(TABLE["tools"]),
        table=TABLE,
    )
    text = attribution.render_document(a_report(), rows)
    assert "iris_query" in text.split("| Tool |")[0]
