# Quickstart: 132 AI Hub on EAP build 139

## Start the AI Hub container

The container ran build 139 until 2026-10-02 and runs 154 now. The 139 one is kept, stopped, as `iad-aihub-iris-139`. The key directory keeps its `aihub139` name.

The key and gateway config live in `~/.config/iris-agentic-dev/aihub139/` (`iris.key`, `CSP.ini`, `CSP.conf`), outside the repo. Never commit them.

```bash
D=~/.config/iris-agentic-dev/aihub139
docker run -d --name iad-aihub-iris -p 11976:1972 \
  -v $D/iris.key:/usr/irissys/mgr/iris.key:ro \
  docker.iscinternal.com/docker-unreleased/intersystems/irishealth:2026.3.0AI.154.0
# wait for "Enabling logons" in messages.log, then (retry if the first try is early).
# A fresh container has an empty ConfigStore descriptor registry; without the rebuild every
# AI.LLM Create fails with ERROR #26414.
printf 'do ##class(Security.Users).UnExpireUserPasswords("*")\ndo ##class(%%ConfigStore.DescriptorManager).RebuildRegistry()\nhalt\n' \
  | docker exec -i iad-aihub-iris iris session IRIS -U %SYS
docker exec iad-aihub-iris iris list   # expect 2026.3.0AI.154
```

## Start the Web Gateway sidecar

The image has no private web server. The sidecar serves 52781 and reaches IRIS at `host.docker.internal:11976` (`docker network create` fails on this host).

`CSP.ini` names server `IRIS` with `Ip_Address=host.docker.internal`, `TCP_Port=11976`, `Username=CSPSystem`, and routes app paths `/`, `/csp` and `/api` to it. `CSP.conf` turns on `CSP On` for `<Location />`, with `CSPModulePath` and `CSPConfigPath` set to `${ISC_PACKAGE_INSTALLDIR}/bin/`.

```bash
docker run -d --name iad-aihub-webgateway -p 52781:80 -v $D:/webgateway-shared \
  -e ISC_CSP_CONF_FILE=/webgateway-shared/CSP.conf -e ISC_CSP_INI_FILE=/webgateway-shared/CSP.ini \
  containers.intersystems.com/intersystems/webgateway:2026.2
curl -s -o /dev/null -w '%{http_code}\n' -u _SYSTEM:SYS http://localhost:52781/api/atelier/   # 200
```

Without the key, every authenticated REST call here returns 503. See research.md R1.

## Unit tests (no container)

```bash
cargo test --features testing --test unit test_aihub_139
cargo test --features testing --test unit test_skill_facts_127
```

## Live tests on 139

```bash
IAD_BINARY=$PWD/target/debug/iris-agentic-dev IAD_AIHUB_WEB_PORT=52781 \
cargo test --features testing --test integration test_aihub_139 -- --include-ignored --test-threads=1
```

With the container stopped, this panics naming `iad-aihub-iris`. To skip instead, add `IAD_ALLOW_SKIP=1`.

## License units

Before the 132 fix (drafts.md B1), each iad process left two or three CSP sessions open on `/api/atelier` for an hour. A binary built from 132 or later ends them on exit. An older binary on `PATH` still leaks them, so check before a run:

```bash
printf 'Write "consumed=",$System.License.LUConsumed(),!\nhalt\n' \
  | docker exec -i iad-aihub-iris iris session IRIS -U %SYS | grep consumed=
```

Above about 90, or when requests start failing with a license error, restart and wait for the gateway:

```bash
docker restart iad-aihub-iris
until curl -sf -o /dev/null -u _SYSTEM:SYS http://localhost:52781/api/atelier/; do sleep 2; done
```

## Real agent turn (spends a few cents)

```bash
IAD_AIHUB_LLM=1 OPENAI_API_KEY=... IAD_BINARY=$PWD/target/debug/iris-agentic-dev \
cargo test --features testing --test integration test_aihub_139_live::aihub_139_real_turn -- --include-ignored --test-threads=1
```

The key reaches the container by variable name only, and the test deletes the Wallet and ConfigStore entries after.

## Upstream file list against GitHub

```bash
cargo test --features testing --test integration test_aihub_139_live::aihub_139_upstream_files -- --include-ignored
```

## Ladder task checks on 139 (no LLM)

```bash
IRIS_WEB_PORT=52781 IRIS_CONTAINER=iad-aihub-iris \
  pytest tests/e2e/skill_eval/test_graded_task_live.py -k aihub -v
```

## Ladder

```bash
python -m tests.e2e.skill_eval.ladder --ladder skill --skill iris-ai-hub --repeats 3 \
  --container iad-aihub-iris --web-port 52781                # holdout: SKILL-24, SKILL-25
python -m tests.e2e.skill_eval.ladder --ladder skill --skill iris-ai-hub --repeats 3 \
  --container iad-aihub-iris --web-port 52781 --side train   # SKILL-22, SKILL-23
python -m tests.e2e.skill_eval.tool_calls list <run_id>
```
