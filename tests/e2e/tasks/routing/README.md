# Routing corpus (spec 128)

`corpus.jsonl` holds 181 prompts an agent might send, each labelled with the skill that should answer it, or `none`. The skill-routing loop scores descriptions against it. `routing-split.toml` freezes which prompts are train and which are holdout.

## Where the prompts came from

`mine.py` pulled 183 prompts from what the repo already has: the first paragraph of every task YAML under `tests/e2e/tasks`, the fire-rate prompts in each skill's `eval.yaml`, and the titles of GitHub issues (`issues.json`, 103 issues). Nobody wrote a prompt for this corpus.

Session transcripts were left out, although FR-001 lists them. The repo is public, and I have no automated way to prove a transcript excerpt is free of customer names, hostnames or credentials.

## Labels

Two Claude sessions labelled every prompt blind. Each saw the prompt and each skill's name, headings and first 25 body lines (`cards.txt`), never its description, and neither saw the prompt's source, because the source field names skills.

- The passes agreed on 176 of 183 prompts (96.2%).
- Five disagreements named two different skills that both fit; those items keep both names as gold, and either counts as correct.
- Two disagreements were one skill against `none`. Exact-match scoring cannot hold both, so they are in `dropped.jsonl` with the reason.

Both passes are kept per item under `labels`.

## Split

An item is train when `sha256(id) mod 100 < 60`, holdout otherwise. The holdout has 80 items: 47 `no-skill`, 26 `paraphrase` and 7 `exact-name`. So only 33 holdout prompts have a skill as gold, and any Recall@1 figure on them has a wide interval. New items join by the same rule; existing ones never move, and `test_corpus.py` fails if one does.
