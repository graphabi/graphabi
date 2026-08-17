# GitHub Action

The root `action.yml` packages GraphABI as a composite GitHub Action. It compares two runs already
stored by an earlier application-specific step, writes a job summary from the versioned report,
and uploads the self-contained HTML report plus its JSON and Markdown summary.

The action does not execute or discover an agent graph, infer contracts, post pull-request
comments, or treat coverage as correctness. It needs no provider API key. Installation and artifact
upload use the network in the normal GitHub Actions environment; comparison itself is local and
deterministic.

## Workflow

Start from [`examples/github-action.yml`](examples/github-action.yml). Replace the action revision
placeholder with the full 40-character commit SHA reviewed by your repository. The example assumes
GraphABI is already a locked development dependency of the integrating project. The trace-recording
step is deliberately application-owned: it must record both named runs into the configured SQLite
database before invoking the action.

```yaml
- name: Compare recorded runs
  id: graphabi
  uses: graphabi/graphabi@FULL_40_CHARACTER_COMMIT_SHA
  with:
    baseline-run: baseline-ci
    candidate-run: candidate-ci
    contract: .graphabi/contracts.yml
    database: .graphabi/traces.db
```

GitHub recommends full commit SHAs because they are immutable. GraphABI will not create a moving
`v1` action tag before explicit release approval.

## Inputs and outputs

`baseline-run`, `candidate-run`, and `contract` are required. `database` defaults to
`.graphabi/demo/traces.db`, and `working-directory` defaults to the checkout root. The artifact is
named `graphabi-report` and retained for 14 days by default.

`fail-on-breaking` and `fail-on-unknown` both default to `true`. They accept only the exact strings
`true` or `false`. The action always generates and uploads a report for GraphABI results before
applying that policy.

Outputs include:

- `exit-code`: the GraphABI CLI result before policy is applied
- `result`: `pass`, `breaking`, `unknown`, or `error`
- `artifact-url`: the authenticated GitHub artifact URL
- `artifact-digest`: the artifact service SHA-256 digest

Exit `0` is allowed, exit `2` is a structural or semantic break, exit `3` is `UNKNOWN` or
`INSUFFICIENT_EVIDENCE`, and any other exit is an operational error. Disabling a failure policy
changes only the workflow step result. It never converts the recorded compatibility status.

## Summary and artifact boundary

The job summary contains structural status, semantic status, the first trace-backed breaking edge
and contract when present, affected downstream nodes, uncertainty count, and observed contract
coverage. It always states that coverage is not correctness.

Only these report files are uploaded:

- `report.json`
- `index.html`
- `summary.md`

Raw SQLite databases and trace exports are excluded. Report serialization masks common credential
shapes and local absolute paths, but it is not a general data-loss-prevention system. Applications
must avoid recording secrets or private data in the first place.

## Release strategy and limits

Until an approved GraphABI release includes the Action, test it from a reviewed full commit SHA.
After release approval, consumers should continue pinning the exact release commit and use
Dependabot to review upgrades. No `v1` tag is created by this work.

The pinned artifact implementation targets GitHub.com and does not support GitHub Enterprise
Server. Self-hosted runners must support the pinned setup action, Python 3.12, and `uv`.
