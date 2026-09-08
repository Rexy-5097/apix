# AgentOS upstream defects and patches

APIx vendors the AgentOS framework from
[Rexy-5097/raptors-way](https://github.com/Rexy-5097/raptors-way).

| Field | Value |
|---|---|
| Upstream commit | `2cf150ff771a9b230bae4602cab83ac2c7a686d8` |
| Upstream date | 2026-07-02 |
| `VERSION` | 1.0.0 |
| Vendored | 2026-09-08 |

This file records every deviation APIx makes from that commit, and every
upstream defect APIx found and chose **not** to fix. Nothing here was changed
silently.

| ID | Defect | Status |
|---|---|---|
| UP-001 | `validate_agentos.py` hardcodes an author-specific absolute path | **Patched** |
| UP-002 | `DOCUMENTATION_INDEX.md` uses absolute `file:///` links | Reported |
| UP-003 | `production_validation/productivity_metrics.csv` is missing | Reported |
| UP-004 | The artifact validator walks the entire repository unscoped | **Patched** |

## Policy

APIx patches vendored framework code only when the framework's own documented
success criterion cannot otherwise be met. Everything else is reported and left
alone, because quietly diverging from a vendored dependency makes the next
upgrade unsafe.

All four defects below should be reported upstream. Recommended as a Task 1
follow-up: open issues on `raptors-way` and offer UP-001 and UP-004 as pull
requests.

---

## UP-001 — `validate_agentos.py` hardcodes an author-specific absolute path

**Status:** PATCHED in APIx (declared).
**Severity:** Blocking. The framework cannot be verified without this fix.

### The defect

`tools/scripts/validate_agentos.py` line 16, as shipped:

```python
# Repository root directory
REPO_ROOT = "/Users/soumyadebtripathy/WorkFlow/agentos-template"
```

The validator resolves every path it checks against this constant. On any
machine other than the original author's, that directory does not exist, so
every structural, architectural and cross-reference check resolves outside the
repository and fails.

### Measured impact

Run on a pristine upstream clone, before any APIx content existed:

```
Readiness Score : 0/100
Overall Status  : FAIL
Missing Dist Files : AGENTOS.md, ARCHITECTURE.md, SUPPORT.md, ... (35 files)
Warning Details:
  - Structural: Missing core root file 'README.md'
  - Structural: Missing core root file 'LICENSE'
  - Architecture: Missing layer directory 'agents'
  ... and 120 more warnings
```

Every one of those files and directories is present in the clone.

This matters because `AGENTOS.md` section 12 states the expected output is
`Overall Grade: 100/100 | Final Status: PASS`, and section 2 step 8 says
initialization may not be declared complete until that score is confirmed. As
shipped, no user can ever satisfy the framework's own initialization protocol.

### The patch

Derived from `__file__`, which is the idiom the sibling script
`tools/scripts/bootstrap_project.py` already uses at its own line 24. The two
scripts now agree on where the repository root is.

```python
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

`os` is already imported at line 9, so the patch adds no dependency.

### Verification

With the patch, on the APIx repository:

```
Structural   : 100/100      Bootstrap   : 100/100
Contract     : 100/100      Harness     : 100/100
Dependency   : 100/100      Loop        : 100/100
Token Budget : 100/100      Validation  : 100/100
Architecture : 100/100      Certification: 100/100
Agent Routing: 100/100      Distribution: 100/100
Workflow     : 100/100      Metrics     : 100/100
Standards    : 100/100      Artifacts   : 100/100
```

16 of 18 categories at 100. The two that are not are UP-002 and UP-003 below.

---

## UP-002 — `DOCUMENTATION_INDEX.md` uses absolute `file:///` links

**Status:** REPORTED, not patched.
**Severity:** Non-blocking. Costs one validator category.

### The defect

`DOCUMENTATION_INDEX.md` links its sibling documents with absolute local URLs:

```
file:///Users/soumyadebtripathy/WorkFlow/agentos-template/AGENTOS.md
file:///Users/soumyadebtripathy/WorkFlow/agentos-template/README.md
...
```

15 distinct links, counted 5 times each by the validator's cross-reference pass,
producing **75 broken references** and `Cross-reference: 0/100`.

### Why APIx did not patch it

It is upstream documentation content, not APIx's to rewrite, and it does not
block the project. Fixing it means editing 15 links in a file APIx does not own,
which would make the next upstream merge conflict for no operational gain.

The correct fix upstream is repository-relative links (`[AGENTOS.md](./AGENTOS.md)`).

### How APIx works around it

`tools/ci/check_markdown_links.py` excludes vendored AgentOS documentation and
checks only APIx-owned Markdown, so these 75 references do not block every APIx
pull request on a defect APIx did not introduce. The AgentOS validator still
reports them in the `validate.yml` workflow, so the signal is not lost.

---

## UP-003 — `production_validation/productivity_metrics.csv` is missing

**Status:** REPORTED, not patched.
**Severity:** Non-blocking. Costs 20 points in one category.

### The defect

The validator's Production RC1 check requires
`production_validation/productivity_metrics.csv`. The shipped template contains
only:

```
production_validation/README.md
production_validation/rc1_validation_report.md
production_validation/readiness_assessment.md
```

Result: `Validation Reports: FAIL`, `Readiness Score: 80/100`.

### Why APIx did not patch it

The missing file is a **metrics** file. Creating one to satisfy a checker would
mean inventing productivity measurements that were never measured. Fabricating
data to turn a check green is precisely the failure mode the APIx dossier is
written against — section 16 requires that unevidenced claims be removed rather
than softened.

An empty or placeholder CSV would be no better: it would report a passing gate
that verifies nothing.

---

## UP-004 — the artifact validator walks the entire repository unscoped

**Status:** PATCHED in APIx (declared).
**Severity:** Blocking for any project that vendors frontmatter-bearing Markdown.

### The defect

`validate_agentos.py::validate_artifacts` walks **every** directory in the
repository and treats any `.md` file beginning with `---` as an AgentOS artifact,
then requires all twelve metadata keys:

```python
for root_dir, _, files in os.walk(self.root):
    if ".git" in root_dir or "node_modules" in root_dir:
        continue
    ...
    if content.startswith("---"):
        # require id, title, version, status, owner, created, modified,
        # related_adr, related_standard, related_checklist,
        # related_workflow, related_agent
```

YAML frontmatter is the universal convention for agent skills, static-site
content and note vaults. Vendoring any of it into an AgentOS project is enough to
floor the Artifacts category.

### Measured impact

APIx vendors 25 Agent Skills under `.claude/skills/`, each carrying a two-key
frontmatter block (`name`, `description`):

```
Artifacts Checked       : 35     (baseline 10)
Missing Metadata Keys   : 300    (baseline 0)
Artifact System Score   : 0/100  (baseline 100/100)
Overall Grade           : 87/100 (baseline 93/100)
```

25 files × 12 required keys = exactly the 300 phantom violations.

The cost is not only six points. Because the category is floored at 0, a
genuinely malformed APIx ADR would no longer move the score — the check stops
being able to report the thing it exists to report.

### The patch

Scope the walk to directories AgentOS owns, matching whole path segments:

```python
vendored = (".git", ".github", "node_modules", ".claude",
            ".venv", "venv", ".mypy_cache", ".pytest_cache")

for root_dir, _, files in os.walk(self.root):
    if any(part in root_dir.split(os.sep) for part in vendored):
        continue
```

### A subtlety worth recording

Upstream's exclusion is the **substring** test `".git" in root_dir`. Because
`".github"` contains `".git"`, it also excluded `.github/` — accidentally. GitHub
issue templates carry GitHub's own frontmatter schema
(`name` / `about` / `title` / `labels`), which is not the AgentOS artifact schema
and should never be measured against it.

Matching whole path segments removes that accident and initially surfaced 33
further phantom violations from `.github/ISSUE_TEMPLATE/*.md`. `.github` is
therefore excluded **explicitly**, so upstream's behaviour is preserved for a
stated reason rather than by coincidence.

### Verification

```
Artifacts Checked       : 10      (identical to pristine baseline)
Missing Metadata Keys   : 0
Artifact System Score   : 100/100
Overall Grade           : 93/100  (identical to pristine baseline)
```

---

## Net effect on APIx

| | Grade | Status |
|---|---|---|
| Upstream template, as shipped, any machine | 0/100 | FAIL |
| Upstream template, pristine, with UP-001 patched | 93/100 | FAIL |
| **APIx after bootstrap, with UP-001 patched** | **93/100** | **FAIL** |

The APIx number is identical to the pristine upstream baseline. **APIx
introduced no regression** — the residual 7 points are entirely UP-002 and
UP-003.

Because `Final Status: PASS` is unreachable with the shipped template, the
`validate.yml` workflow enforces **no regression below 93** rather than a
literal 100. That threshold lives in `AGENTOS_BASELINE_GRADE` and should be
raised — never lowered — as upstream defects are fixed.

## Reproducing these measurements

```bash
# Pristine upstream baseline
git clone https://github.com/Rexy-5097/raptors-way.git /tmp/agentos-pristine
cd /tmp/agentos-pristine
sed -i 's|^REPO_ROOT = .*|REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))|' \
  tools/scripts/validate_agentos.py
python tools/scripts/validate_agentos.py | grep -E 'Overall Grade|Final Status'

# APIx
cd /path/to/apix
python tools/scripts/validate_agentos.py | grep -E 'Overall Grade|Final Status'
```
