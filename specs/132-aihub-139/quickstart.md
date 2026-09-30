# Quickstart: 132 AI Hub on EAP build 139

## Start the 139 container

```bash
docker run -d --name iad-aihub-iris -p 11976:1972 -p 52781:52773 \
  docker.iscinternal.com/docker-unreleased/intersystems/irishealth:2026.3.0AI.139.0
# wait for "Enabling logons" in messages.log, then:
printf 'do ##class(Security.Users).UnExpireUserPasswords("*")\nhalt\n' \
  | docker exec -i iad-aihub-iris iris session IRIS -U %SYS
docker exec iad-aihub-iris iris list   # expect 2026.3.0AI.139
```

It needs no license key to start, but with no key it has one license unit and no web server. See research.md R1.

## Unit tests (no container)

```bash
cargo test --features testing --test unit test_aihub_139
cargo test --features testing --test unit test_skill_facts_127
```

## Live tests on 139

```bash
IAD_BINARY=$PWD/target/debug/iris-agentic-dev \
cargo test --features testing --test integration test_aihub_139 -- --include-ignored --test-threads=1
```

With the container stopped, this panics naming `iad-aihub-iris`. To skip instead, add `IAD_ALLOW_SKIP=1`.

## Real agent turn (spends a few cents)

```bash
IAD_AIHUB_LLM=1 OPENAI_API_KEY=... IAD_BINARY=$PWD/target/debug/iris-agentic-dev \
cargo test --features testing --test integration test_aihub_139_real_turn -- --include-ignored --test-threads=1
```

The key reaches the container by variable name only, and the test deletes the Wallet and ConfigStore entries after.

## Upstream file list against GitHub

```bash
cargo test --features testing --test integration test_aihub_139_upstream_files -- --include-ignored
```

## Ladder (needs a license key, see research.md R1)

```bash
python -m tests.e2e.skill_eval.ladder --ladder skill --skill iris-ai-hub --repeats 3 \
  --container iad-aihub-iris --web-port 52781                # holdout: SKILL-24, SKILL-25
python -m tests.e2e.skill_eval.ladder --ladder skill --skill iris-ai-hub --repeats 3 \
  --container iad-aihub-iris --web-port 52781 --side train   # SKILL-22, SKILL-23
python -m tests.e2e.skill_eval.tool_calls list <run_id>
```

## Web Gateway sidecar (only once a key is mounted)

`/tmp/iad-aihub-wg/CSP.ini` (use the IRIS container's bridge IP; `docker network create` fails on this host):

```ini
[SYSTEM]
IRISCONNECT_LIBRARY_PATH=/opt/webgateway/bin
System_Manager=*.*.*.*
[SYSTEM_INDEX]
IRIS=Enabled
[IRIS]
Ip_Address=<iad-aihub-iris bridge IP>
TCP_Port=1972
Minimum_Server_Connections=3
Username=CSPSystem
Password=SYS
[APP_PATH_INDEX]
/=Enabled
/csp=Enabled
/api=Enabled
[APP_PATH:/]
Default_Server=IRIS
[APP_PATH:/csp]
Default_Server=IRIS
[APP_PATH:/api]
Default_Server=IRIS
```

`CSP.conf` turns on `CSP On` for `<Location />`, with `CSPModulePath` and `CSPConfigPath` set to `${ISC_PACKAGE_INSTALLDIR}/bin/`.

```bash
docker run -d --name iad-aihub-webgateway -p 52781:80 -v /tmp/iad-aihub-wg:/webgateway-shared \
  -e ISC_CSP_CONF_FILE=/webgateway-shared/CSP.conf -e ISC_CSP_INI_FILE=/webgateway-shared/CSP.ini \
  containers.intersystems.com/intersystems/webgateway:2026.2
curl -s -o /dev/null -w '%{http_code}\n' -u _SYSTEM:SYS http://localhost:52781/api/atelier/   # 200 when licensed
```

To give the gateway 52781, recreate the IRIS container without `-p 52781:52773`.
