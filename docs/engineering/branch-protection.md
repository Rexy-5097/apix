# Branch protection for `main`

> **STATUS: APPLIED — 2026-09-08, by @Rexy-5097.**
>
> Every setting below is in force and was verified by reading the protection
> back from the API, not assumed from a successful write. `Rexy-5097/apix` is
> public, so the GitHub Free plan permits classic branch protection in full —
> the private-repo limitation noted at the bottom of this file did not apply.
>
> Verify at any time:
> `gh api repos/Rexy-5097/apix/branches/main/protection`

`main` is the protected integration branch. Every merged pull request should
leave it in a state a teammate could clone and build.

## Target configuration

| Setting | Target | Why |
|---|---|---|
| Require a pull request before merging | **On** | No direct pushes to `main`, including documentation |
| Required approvals | **1** | The domain owner who did not write it reviews it |
| Dismiss stale approvals on new commits | **On** | An approval describes a diff, not a branch |
| Require review from Code Owners | **On** | Makes `.github/CODEOWNERS` binding rather than advisory |
| Require status checks to pass | **On** | |
| Require branches to be up to date | **On** | Catches semantic conflicts CI would otherwise miss |
| Block force pushes | **On** | `main` history is shared |
| Block deletions | **On** | |
| Require conversation resolution | **On** | An unresolved review comment is unfinished work |
| Require linear history | **On** | Pairs with squash-merge; keeps checkpoints one SHA each |
| Enforce for administrators | **On** | A rule the owner can bypass is a convention, not a rule |

### Required status checks

Exact job names from the workflows in `.github/workflows/`:

```
Architecture boundary (statistics determinism)     # ci.yml — never make this advisory
Lint (ruff)                                        # ci.yml
Types (mypy)                                       # ci.yml
Tests (pytest)                                     # ci.yml
AgentOS Health Check                               # validate.yml
YAML Validation                                    # lint.yml
Internal link check                                # lint.yml
```

The architecture check is the one that must never be downgraded. It enforces the
deterministic statistics boundary from dossier section 05, which is a published
methodology guarantee.

## Applying it

Status checks can only be marked *required* after they have reported at least
once, so the order matters:

1. Create the repository under `Rexy-5097`.
2. Push `main` and open the bootstrap pull request.
3. Let CI run once so GitHub learns the check names.
4. Apply protection with the command below.
5. Verify, and update the status line at the top of this file.

### With the GitHub CLI

Authenticate as the repository owner first — protection is an admin operation:

```bash
gh auth switch --user Rexy-5097
gh auth status
```

```bash
gh api --method PUT repos/Rexy-5097/apix/branches/main/protection \
  --input docs/engineering/branch-protection.json
```

The payload lives beside this file in
[`branch-protection.json`](branch-protection.json).

### Verifying

```bash
gh api repos/Rexy-5097/apix/branches/main/protection | \
  python -m json.tool
```

Confirm `required_pull_request_reviews.require_code_owner_reviews` is `true`,
`enforce_admins.enabled` is `true`, and every check above appears in
`required_status_checks.contexts`.

## Known limitations — report these honestly, do not paper over them

- **Private repositories on the GitHub Free plan cannot use branch protection.**
  If `Rexy-5097/apix` is private on Free, the API returns `403 Upgrade to GitHub
  Pro or make this repository public to use this feature`. The options are: make
  the repository public, upgrade the plan, or accept that protection is
  unavailable and say so. Do not claim protection is configured when it is not.
- **Rulesets vs. branch protection.** Repository *rulesets* are the newer
  mechanism and are available on Free for public repositories. If classic branch
  protection is unavailable, a ruleset targeting `main` is the fallback; record
  which mechanism is actually in force.
- **Required approvals need a second account with write access.** With one
  collaborator, `enforce_admins` plus one required approval means the owner
  cannot merge their own PR. Confirm all three contributors have write access
  before enabling, or the bootstrap PR cannot be merged at all.
- **Code Owner reviews require the owners to have access.** `@slazyverse` and
  `@Basant-creator` must be collaborators, or their CODEOWNERS entries silently
  do nothing.
