# Content corpus (spec 130)

`corpus.jsonl` holds prompts for the eight skills 130 wrote or corrected, plus negatives. `optimize run --surface content-descriptions` scores them together with the 128 routing corpus in `../routing/`, and may change only those eight descriptions.

## Where the prompts came from

I wrote them. The 128 corpus was mined from what the repo already had and holds few prompts about query plans, test discovery, production state or namespace switching, so these fill that gap. That makes them different from the 128 corpus: they are my guess at how someone asks, not a record of how anyone did. A lift measured on them says the new descriptions route my phrasings better and no more.

Each prompt describes a problem or a task. One names a skill, because the product and the skill share a name: "Which toml keys configure the connection for iris-agentic-dev?" is `exact-name`.

## Labels

Two Claude sessions labelled every prompt blind, from `cards.txt` (each skill's name, headings and first 25 body lines, no description, regenerated after 130 added `iris-query-plans`). Neither saw which skill I wrote a prompt for.

When both passes named the same skill, that is the gold. When they named two different skills, both are gold. When one said `none` and the other a skill, the item is in `dropped.jsonl` with both labels. Both passes are kept per item under `labels`.

- The passes named the same skill for 52 of 54 prompts.
- The other two ("What are the rules I should follow when writing a new ObjectScript class method" and the single-dollar `$OK` question) split between `objectscript-guardrails` and `objectscript-review`, and keep both as gold.
- None split between a skill and `none`, so `dropped.jsonl` is empty.
- Two prompts I wrote for one of the eight went to a skill outside them: the review request to `objectscript-review`, and "compiler says 0 errors but the method throws `<UNDEFINED>`" to `objectscript-debugging`, not `objectscript-tdd`. The labels stand. I did not relabel toward what I meant.

## Split

Ids are `c-` and the first ten hex digits of the prompt's sha256, so they cannot collide with the `r-` routing ids. The split is the 128 rule: train when `sha256(id) mod 100 < 60`, holdout otherwise. The holdout has 25 items: 20 `paraphrase`, 4 `no-skill` and 1 `exact-name`. `routing-split.toml` freezes it, and `test_content_surface.py` fails if an item moves or the file stops covering the corpus.
