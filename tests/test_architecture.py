"""Architectural boundary enforcement for the APIx statistics layer.

Dossier v2.1 section 05 states the rule once and requires it enforced everywhere:

    statistics calculates, machine learning explains.

The published index must be reproducible from
``(snapshot_id, methodology_version, weight_version, code_version)`` alone.
A stochastic dependency anywhere under ``statistics/`` breaks that guarantee,
so this test fails the build rather than letting it merge.

Design notes
------------
The check is **static**. It parses each module under ``statistics/`` with
``ast`` and never imports it. Importing the layer to inspect its imports would
require the package to be installable and side-effect free, would execute module
level code in CI, and would miss imports guarded behind ``if`` blocks. Parsing
sees every ``import`` statement regardless of whether it would execute.

Dossier section 12 ("Removal test"): delete the Claude API integration and the
entire analytics layer, and collection, cleaning, deduplication, Jevons,
Young/Modified Laspeyres, TPD and index publication must all still work. This
test is what tells you where that boundary was violated.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The statistics layer. Deterministic by construction.
STATISTICS_ROOT = REPO_ROOT / "src" / "apix" / "statistics"

# Dossier section 05, verbatim. Do not extend this set without a methodology
# review: adding a name here is a statement about reproducibility, not style.
FORBIDDEN: frozenset[str] = frozenset(
    {
        "sklearn",
        "lightgbm",
        "xgboost",
        "torch",
        "anthropic",
        "openai",
    }
)

# Layers that are allowed to read the index but never to write it. The
# statistics layer must not depend on them either, or the removal test in
# dossier section 12 fails.
#
# Under the src layout these are submodules of `apix`, so an absolute import
# reads `apix.analytics`. The detector records top-level packages, so it also
# checks the second segment for imports rooted at `apix`.
FORBIDDEN_LAYERS: frozenset[str] = frozenset({"analytics", "ai"})


@dataclass(frozen=True)
class Module:
    """A parsed Python module and the top-level packages it imports."""

    name: str
    path: Path
    imports: frozenset[str]
    qualified_imports: frozenset[str] = frozenset()


def _top_level(dotted: str) -> str:
    """Return the root package of a dotted import path."""
    return dotted.split(".", 1)[0]


def _first_two(dotted: str) -> str:
    """Return the first two segments, e.g. ``apix.analytics``.

    Needed because ADR-0061's src layout makes every in-project import start
    with ``apix``; the layer being imported is the *second* segment.
    """
    return ".".join(dotted.split(".")[:2])


def _display_name(path: Path) -> str:
    """Repo-relative path for error messages, falling back to the full path.

    ``Path.relative_to`` raises when the two paths sit on different Windows
    drives, which is exactly what happens when the detector's own meta-tests
    walk a pytest ``tmp_path`` on C: while the repository is on D:.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _walk_imports(root: Path) -> list[Module]:
    """Statically collect the imports of every Python module under ``root``."""
    modules: list[Module] = []

    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        imported: set[str] = set()
        qualified: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(_top_level(alias.name))
                    qualified.add(_first_two(alias.name))
            # ``node.level > 0`` is a relative import: it cannot reach another
            # top-level layer, so it is always in-bounds and is skipped here.
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(_top_level(node.module))
                qualified.add(_first_two(node.module))

        modules.append(
            Module(
                name=_display_name(path),
                path=path,
                imports=frozenset(imported),
                qualified_imports=frozenset(qualified),
            )
        )

    return modules


def test_statistics_root_exists() -> None:
    """Guard against the boundary test silently passing on a moved directory.

    If ``statistics/`` is renamed, ``_walk_imports`` would return an empty list
    and every assertion below would vacuously pass. This test is what stops the
    architectural guarantee from quietly evaporating during a refactor.
    """
    assert STATISTICS_ROOT.is_dir(), (
        f"Expected the statistics layer at {STATISTICS_ROOT}. "
        "If the layer moved, update tests/test_architecture.py deliberately — "
        "this boundary is a published methodology guarantee, not a lint rule."
    )


def test_statistics_layer_is_deterministic() -> None:
    """No module under statistics/ may import a stochastic dependency."""
    violations: list[str] = []

    for module in _walk_imports(STATISTICS_ROOT):
        offending = module.imports & FORBIDDEN
        if offending:
            violations.append(f"  {module.name} imports {sorted(offending)}")

    assert not violations, (
        "The statistics layer imports a stochastic dependency:\n"
        + "\n".join(violations)
        + "\n\nThe published index must be reproducible from "
        "(snapshot_id, methodology_version, weight_version, code_version) alone.\n"
        "Statistics calculates; ML/AI explains. Move this code to analytics/ or ai/."
    )


def _upper_layer_imports(module: Module) -> set[str]:
    """Upper-layer packages this module imports, under the src layout.

    ADR-0061 moved the layers under ``src/apix/``, so an absolute import of the
    analytics layer reads ``apix.analytics`` — whose *top-level* package is
    ``apix``. Matching only top-level names would therefore never fire, leaving
    INV-11 unenforced while appearing to pass. This inspects the second segment
    whenever the first is ``apix``.
    """
    offending = module.imports & FORBIDDEN_LAYERS
    return offending | (module.qualified_imports & {f"apix.{layer}" for layer in FORBIDDEN_LAYERS})


def test_statistics_layer_does_not_depend_on_upper_layers() -> None:
    """statistics/ must not import analytics/ or ai/.

    Dossier section 12 removal test: deleting analytics and ai must leave the
    index engine working. An import in this direction breaks that.
    """
    violations: list[str] = []

    for module in _walk_imports(STATISTICS_ROOT):
        offending = _upper_layer_imports(module)
        if offending:
            violations.append(f"  {module.name} imports {sorted(offending)}")

    assert not violations, (
        "The statistics layer depends on a layer above it:\n"
        + "\n".join(violations)
        + "\n\nLayer 3 reads the index and never writes it. Remove analytics/ and "
        "ai/ entirely and the index must still publish."
    )


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN))
def test_forbidden_dependency_is_detected(forbidden: str, tmp_path: Path) -> None:
    """The detector itself must actually detect. A boundary test that cannot
    fail is worse than no boundary test, because it reports safety it is not
    checking. This plants each forbidden import and asserts it is caught.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(f"import {forbidden}\n", encoding="utf-8")

    modules = _walk_imports(tmp_path)

    assert len(modules) == 1
    assert modules[0].imports & FORBIDDEN == {forbidden}


def test_detector_sees_from_imports(tmp_path: Path) -> None:
    """``from sklearn.linear_model import X`` must be caught, not just ``import sklearn``."""
    planted = tmp_path / "planted.py"
    planted.write_text("from sklearn.linear_model import LinearRegression\n", encoding="utf-8")

    modules = _walk_imports(tmp_path)

    assert modules[0].imports & FORBIDDEN == {"sklearn"}


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_LAYERS))
def test_upper_layer_import_is_detected_under_the_src_layout(layer: str, tmp_path: Path) -> None:
    """Regression for a boundary check that could not fire.

    Before ADR-0061 the layers sat at the repository root, so ``import
    analytics`` had ``analytics`` as its top-level package and the check worked.
    After the move to ``src/apix/`` the same import reads ``apix.analytics``,
    whose top-level package is ``apix`` — so the check silently stopped being
    able to detect anything while continuing to pass.

    INV-11 is the removal test of dossier section 12. A check that reports a
    safety it is not measuring is worse than no check.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(f"from apix.{layer}.thing import f\n", encoding="utf-8")

    module = _walk_imports(tmp_path)[0]
    assert _upper_layer_imports(module) == {f"apix.{layer}"}


def test_detector_ignores_relative_imports(tmp_path: Path) -> None:
    """Relative imports stay inside the layer and must not be flagged."""
    planted = tmp_path / "planted.py"
    planted.write_text("from .jevons import short_relative\n", encoding="utf-8")

    modules = _walk_imports(tmp_path)

    assert not (modules[0].imports & FORBIDDEN)
    assert not (modules[0].imports & FORBIDDEN_LAYERS)
