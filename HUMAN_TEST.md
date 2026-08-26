# External-user human test protocol

Goal: ask 5 real Python developers with no prior GraphABI context to try the alpha independently.
Do not coach them beyond the written instructions. Do not count maintainers, bots, Codex, Claude,
or scripted CI.

## Setup

- Participant uses Python 3.12 or 3.13 on their own machine.
- Participant starts from `python -m pip install graphabi==0.1.0a3`.
- Participant may read the README and docs but should not receive live maintainer guidance during
  the timed task.
- Participant must use synthetic or throwaway data only.

## Tasks to time

Record elapsed time and whether the participant completed each task:

- Install package from PyPI.
- Run `graphabi doctor`.
- Run `graphabi demo --allow-breaking`.
- Open the generated report.
- Explain why the demo is `Structural compatibility: PASS` and `Semantic compatibility: FAIL`.
- Run `graphabi init` in a clean project.
- Identify what the starter contract does and does not enforce.
- Capture a first real trace from a supported framework or explain why they cannot.
- Capture baseline and candidate traces.
- Run `graphabi compare`.
- Explain `PASS`, `FAIL`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE`, and coverage.
- Find where to ask for help or report a bug.

## Questions

Ask these after the attempt:

- Where did you first get stuck?
- Which command or document gave you enough context to continue?
- Did `UNKNOWN` mean broken, uncertain, or successful to you?
- Did you trust the finding? Why or why not?
- Would you use this again on an agent-system change?
- What did you expect GraphABI to do that it does not do?
- What data would you refuse to put into a local trace or report?
- What one document or command should change before the next tester?

## Recording template

```text
Participant:
Date:
Python:
OS:
Framework attempted:

Install success:
Time to first demo:
Time to first report:
Time to first real trace:
Time to first comparison:

Got stuck at:
Understood UNKNOWN:
Trusted finding:
Would use again:
Expected unsupported behavior:
Follow-up issue filed:
Notes:
```

Store only consented notes. Do not publish names or quotes without permission.
