# GitHub maintainer configuration

This records the intended public-repository settings for GraphABI. It is guidance, not evidence
that a setting is currently enabled. Verify live settings before every release.

## Main-branch protection recommendation

GraphABI currently has one maintainer. Do not require an approving review yet: GitHub does not
allow authors to approve their own pull requests, so one required approval would make routine
maintenance depend on another account.

After the repository is public and both matrix jobs have completed successfully at least once,
create a ruleset targeting `main` with:

- block force pushes and branch deletion;
- require the `quality (3.12)` and `quality (3.13)` status checks;
- require branches to be up to date before merge;
- require conversation resolution;
- allow repository administrators a documented emergency bypass;
- leave required approving reviews at zero while there is only one active maintainer.

When a second reliable maintainer is active, require one approval, dismiss stale approvals after
new commits, and require CODEOWNER review for contract, comparison, reporting, security-policy,
and workflow changes. Re-evaluate whether the administrator bypass is still needed.

Do not require signed commits until every maintainer has tested the signing workflow. Do not enable
merge queues or deployment gates until they solve an observed problem.

## Publication checklist

Before changing repository visibility:

1. Confirm local bootstrap, lint, typecheck, tests, demo, benchmark, and distributions from a clean
   clone.
2. Confirm GitHub CI and release dry run pass on the exact `main` commit.
3. Confirm all commit authors and committers use an approved noreply identity.
4. Review repository files and generated reports for credentials and personal data.
5. Make `graphabi/graphabi`, `graphabi/.github`, and `graphabi/graphabi.github.io` public only with
   explicit maintainer approval.
6. Enable GitHub Pages from `graphabi/graphabi.github.io` branch `main`, directory `/ (root)`.
7. Upload `docs/assets/brand/social-preview.png` through repository settings.
8. Create the `Framework Integrations` and `Research` Discussion categories in the GitHub UI; the
   public API does not currently expose category creation.
9. Decide explicitly whether to enable Private Vulnerability Reporting and secret-scanning
   features before changing those security settings.
10. Validate public links, the organization profile, Pages, issue forms, and Discussions from a
    signed-out browser.

## First release checklist

Publishing `v0.1.0-alpha.1` is a separate approval boundary. After the public repository and Pages
are verified, review `docs/releases/v0.1.0-alpha.1.md`, tag the exact tested commit, create the
GitHub release, and attach the wheel and source distribution if desired. Do not publish to PyPI.
