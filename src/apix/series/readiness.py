"""Publication readiness — the layer that is allowed to say no.

The mathematics can always produce a number. This module decides whether the
number may be **published**, and it is deliberately separate from the code that
computes it.

Three classes of output, never confused, and every payload says which it is:

==============  ==========================================================
``PRODUCTION``  A real index from real observations meeting every guard.
                **APIx has never produced one.**
``RESEARCH``    Real observations, but a guard is unmet -- so descriptive
                statistics only, never presented as an index.
``DEMO``        Deterministic replay of a synthetic fixture. Exercises the
                pipeline. Never a claim about the market.
==============  ==========================================================

The readiness states extend the existing guards rather than replacing them.
:mod:`apix.statistics.index.chaining` still refuses an index without a matched
``t / t-7`` pair, and :func:`apix.statistics.index.publication.publish` still
requires an explicit coverage denominator. This module reports *why* in a form a
dashboard and an API can render.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReadinessState(Enum):
    """Why a series may or may not be published."""

    #: Every guard met. Publishable as an official index.
    READY = "READY"
    #: Publishable with a stated caveat, short of full production standing.
    PROVISIONAL = "PROVISIONAL"
    #: Spec I coverage below threshold, or the denominator undefined (AMB-8).
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    #: Spec C.1 needs a matched ``t / t-7`` pair and no prior wave exists.
    MISSING_PREVIOUS_PERIOD = "MISSING_PREVIOUS_PERIOD"
    #: No source cleared the compliance gate, so no quote could be collected.
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    #: Collection ran and produced no admissible observation.
    NO_VALID_QUOTES = "NO_VALID_QUOTES"
    #: An open methodology ruling blocks publication (AMB-8, AMB-9).
    METHODOLOGY_INCOMPLETE = "METHODOLOGY_INCOMPLETE"
    #: The PS-required benchmark comparison has not been satisfied.
    BACKTEST_INCOMPLETE = "BACKTEST_INCOMPLETE"


class OutputClass(Enum):
    """What a payload is. Must accompany every published figure."""

    PRODUCTION = "PRODUCTION"
    RESEARCH = "RESEARCH"
    DEMO = "DEMO"


@dataclass(frozen=True, slots=True)
class SeriesReadiness:
    """A readiness verdict, with every blocker named."""

    state: ReadinessState
    output_class: OutputClass
    publishable: bool
    blockers: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "output_class": self.output_class.value,
            "publishable": self.publishable,
            "blockers": list(self.blockers),
            "detail": self.detail,
        }


def assess(
    *,
    collection_waves: int,
    matched_pairs: int,
    admissible_observations: int,
    cleared_sources: int,
    coverage_denominator_defined: bool,
    open_blocking_ambiguities: tuple[str, ...] = (),
    basket_is_publication_grade: bool = False,
    backtest_satisfied: bool = False,
    is_fixture: bool = False,
) -> SeriesReadiness:
    """Decide whether a series may be published, and say why not.

    Order matters: the **most fundamental** blocker is reported as the state,
    while every applicable blocker is listed. A caller that has no observations
    and no matched pair should be told about the observations first, because
    fixing the pair presupposes them.
    """
    blockers: list[str] = []

    if is_fixture:
        return SeriesReadiness(
            state=ReadinessState.PROVISIONAL,
            output_class=OutputClass.DEMO,
            publishable=False,
            blockers=("SYNTHETIC FIXTURE — not market data",),
            detail=(
                "Deterministic replay of a controlled fixture. It demonstrates that the "
                "pipeline computes an index end to end. It is NOT a measurement of any market "
                "and must never be presented as one."
            ),
        )

    if admissible_observations == 0:
        state = (
            ReadinessState.SOURCE_BLOCKED
            if cleared_sources == 0
            else ReadinessState.NO_VALID_QUOTES
        )
        blockers.append(
            "no source cleared the compliance gate, so no quote could be collected"
            if cleared_sources == 0
            else "collection ran but produced no admissible observation"
        )
        return SeriesReadiness(
            state=state,
            output_class=OutputClass.RESEARCH,
            publishable=False,
            blockers=tuple(blockers),
            detail=(
                "No admissible observation exists, so there is nothing to publish. This is "
                "reported as a coverage loss attributed to us, never as an absence of flights."
            ),
        )

    if matched_pairs == 0:
        blockers.append(
            f"spec C.1 is LOCKED at I(c,t) = I(c,t-7) x J(c,t); {collection_waves} collection "
            "wave(s) held, so zero matched pairs exist"
        )
    if not coverage_denominator_defined:
        blockers.append(
            "spec I gates on a share of expected cells and AMB-8 leaves 'expected cell' "
            "undefined, so no coverage figure can be computed"
        )
    for amb in open_blocking_ambiguities:
        blockers.append(f"{amb} is OPEN and blocking; it may not be resolved by choosing a value")
    if not basket_is_publication_grade:
        blockers.append(
            "the route basket is not publication grade — weights are provisional pending OQ-4"
        )
    if not backtest_satisfied:
        blockers.append("the PS-required benchmark backtest is not satisfied")

    if not blockers:
        return SeriesReadiness(
            state=ReadinessState.READY,
            output_class=OutputClass.PRODUCTION,
            publishable=True,
            blockers=(),
            detail="Every guard met.",
        )

    if matched_pairs == 0:
        state = ReadinessState.MISSING_PREVIOUS_PERIOD
    elif not coverage_denominator_defined:
        state = ReadinessState.INSUFFICIENT_COVERAGE
    elif open_blocking_ambiguities:
        state = ReadinessState.METHODOLOGY_INCOMPLETE
    elif not backtest_satisfied:
        state = ReadinessState.BACKTEST_INCOMPLETE
    else:
        state = ReadinessState.INSUFFICIENT_COVERAGE

    return SeriesReadiness(
        state=state,
        output_class=OutputClass.RESEARCH,
        publishable=False,
        blockers=tuple(blockers),
        detail=(
            "Real observations exist and pass the stages above the longitudinal step, so "
            "descriptive statistics are reportable as RESEARCH output. No index level is "
            "published, and the guards refuse rather than inventing one."
        ),
    )


__all__ = ["OutputClass", "ReadinessState", "SeriesReadiness", "assess"]
