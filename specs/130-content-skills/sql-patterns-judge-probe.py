"""Judge probe for SQLCODE-SILENT: which answers does the real judge pass?"""
import json, sys, yaml
from tests.e2e.skill_eval.judge import score_result

task = yaml.safe_load(open("tests/e2e/tasks/skills/targeted/SQLCODE-SILENT.yaml"))
task = {**task, "category": task.get("category", "")}

READ = [
    {"role": "assistant", "tool_name": "iris_doc", "args": {"mode": "get", "name": "EvalDemo.PatientLookup.cls"},
     "tool_result": task["fixtures"][0]["content"]},
]

def put(body):
    return {"role": "assistant", "tool_name": "iris_doc",
            "args": {"mode": "put", "name": "EvalDemo.PatientLookup.cls", "compile": True, "content": body},
            "tool_result": '{"compiled":true,"compile_errors":[],"success":true}', "text": ""}

def method(check):
    return ("Class EvalDemo.PatientLookup Extends %RegisteredObject\n{\n\n"
            "ClassMethod FindPatient(pMRN As %String) As %String\n{\n"
            "    Set result = \"\"\n"
            "    &sql(SELECT Name INTO :result FROM EvalDemo_PatientLookup WHERE MRN = :pMRN)\n"
            f"{check}"
            "    Quit result\n}\n\n}\n")

P2 = method("    If SQLCODE = 100 { Quit \"\" }\n    If SQLCODE '= 0 { Quit \"\" }\n")
P3 = method("    If SQLCODE = 100 { Quit \"\" }\n    If SQLCODE < 0 {\n        Throw ##class(%Exception.SQL).CreateFromSQLCODE(SQLCODE, %msg)\n    }\n")
P4 = method("    If SQLCODE = 100 { Quit \"\" }\n    If SQLCODE < 0 { Quit \"ERROR: \"_SQLCODE }\n")

probes = {
    "P1_untouched": READ + [{"role": "assistant", "text":
        "The method looks correct: `If SQLCODE` is false when SQLCODE=0, so a found row is returned. No change needed."}],
    "P2_rubric_literal": READ + [put(P2), {"role": "assistant", "text":
        "Fixed. The check now uses `If SQLCODE '= 0` for errors and handles SQLCODE=100 (no rows) separately:\n\n" + P2}],
    "P3_iris_correct": READ + [
        {"role": "assistant", "tool_name": "iris_execute", "args": {"code": "w ##class(EvalDemo.PatientLookup).FindPatient(\"M1\")"},
         "tool_result": '{"output":""}'},
        {"role": "assistant", "tool_name": "iris_query", "args": {"query": "SELECT Name FROM EvalDemo_PatientLookup"},
         "tool_result": "SQLCODE -30: Table 'SQLUSER.EVALDEMO_PATIENTLOOKUP' not found"},
        put(P3), {"role": "assistant", "text":
        "`If SQLCODE` is not itself wrong: SQLCODE=0 is falsy, so a found row already reached `Quit result`. "
        "The silent bug is that the check lumps SQLCODE=100 (no row) together with negative SQLCODEs (errors), so every "
        "SQL error comes back as \"\", indistinguishable from 'no patient'. Here that is hiding a real error: the query "
        "gets SQLCODE -30 because the table does not exist, so the method returns \"\" on every call. I split the "
        "cases: 100 returns \"\", a negative SQLCODE throws with %msg, 0 returns the name:\n\n" + P3}],
    "P4_minimal_correct": READ + [put(P4), {"role": "assistant", "text":
        "Fixed: no-row (SQLCODE=100) returns \"\" and an SQL error (SQLCODE<0) is now reported instead of being "
        "returned as an empty match:\n\n" + P4}],
}

out = {}
ONLY = sys.argv[2:] or list(probes)
for name, turns in [(n, probes[n]) for n in ONLY]:
    out[name] = []
    for i in range(3):
        v = score_result(task, {"transcript": turns, "tool_call_count": sum(1 for t in turns if t.get("tool_name")), "path": "B"})
        out[name].append((v.get("score"), v.get("reasoning")))
        print(name, i, v.get("score"), "|", v.get("reasoning"), flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
