"""What the jury-facing page is allowed to say, and what it must never show.

`test_observed_panel.py` already checks that the dashboard's figures agree with
the contract. This file guards the two failure modes that check cannot see:

1. **A figure that is right in the markup but wrong on screen.** Every large
   number animates, and an animated number whose static text is ``0`` renders
   "0 screenshots audited" to anyone whose script is blocked, and for the first
   second to everyone else. A page that displays a *false* number is worse than
   one that displays none, so the static text must already be the truth.

2. **A claim the evidence does not carry.** The panel is one route, one carrier,
   one wave, with no published index and no implemented TPD. Calling it a
   quality-adjusted national index would be false, and explaining an observed
   difference with an untested cause would be storytelling.

Both were real defects, not hypotheticals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "data" / "dashboard.html"


@pytest.fixture(scope="module")
def html() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered(html: str) -> str:
    """The page as text — what a reader actually sees.

    `<style>` and `<script>` bodies are dropped whole, not just their tags:
    a spacing token of `116px` or a hex colour ending `33` is not a rendered
    number, and counting it as one makes the guard cry wolf.
    """
    body = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]+>", " ", body).split())


@pytest.fixture(scope="module")
def panel() -> dict:
    return json.loads((ROOT / "data" / "panel.json").read_text(encoding="utf-8"))


# ── 1. no animated figure may render a false value ──────────────────────────


def test_every_counter_shows_its_true_value_before_any_script_runs(html: str) -> None:
    """The static text of a counter IS the figure; the animation only replays it.

    Caught in review: every headline number shipped as `data-count="157">0<`,
    so a blocked script showed "0 screenshots audited" and "+0%".
    """
    counters = re.findall(r'data-count="([^"]+)"[^>]*>([^<]*)<', html)
    assert counters, "no counters found — the selector has drifted"
    wrong = [
        (target, shown)
        for target, shown in counters
        if shown.strip().lstrip("+").rstrip("%") != target
    ]
    assert not wrong, f"counters whose static text is not the true figure: {wrong}"


def test_no_counter_falls_back_to_zero(html: str) -> None:
    assert not re.search(r'data-count="(?!0")[^"]+"[^>]*>\s*\+?0%?\s*<', html)


# ── 2. the audit ladder must close, and derive from the contract ────────────


def test_the_audit_ladder_closes_and_comes_from_the_contract(panel: dict, rendered: str) -> None:
    """152 minus 122 = 30, plus 5 = 157 = 35 retained plus 122 excluded.

    The two halves are the same accounting seen twice: the survivors of the file
    corpus are exactly the hashed observations, and the chat-image batch is
    exactly the weaker-provenance group.
    """
    ev = panel["quality"]["evidence_counts"]
    excluded = panel["exclusions_total"]
    retained = panel["quality"]["valid_observations"]
    corpus = excluded + ev["PRIMARY_HASHED"]
    audited = corpus + ev["SECONDARY_CHAT_IMAGE"]

    assert audited == excluded + retained, "the ladder does not close in the contract"
    for value in (corpus, excluded, ev["PRIMARY_HASHED"], ev["SECONDARY_CHAT_IMAGE"], audited):
        assert str(value) in rendered, f"{value} is missing from the rendered ladder"


def test_the_weaker_provenance_bucket_is_derived_not_guessed(panel: dict, rendered: str) -> None:
    """The chat-image batch is one specific bucket, and it is not the last one.

    Caught in review: the ladder labelled it with the final APW bucket, which is
    a different bucket entirely and rests on hashed evidence.
    """
    chat = sorted(
        {o["apw"] for o in panel["observations"] if o["evidence"] == "SECONDARY_CHAT_IMAGE"}
    )
    hashed = sorted({o["apw"] for o in panel["observations"] if o["evidence"] == "PRIMARY_HASHED"})
    assert chat, "no secondary-evidence observations — this guard would pass blind"
    assert not (set(chat) & set(hashed)), "a bucket mixes evidence grades; the label must say so"

    label = ", ".join(f"T+{a}" for a in chat)
    assert f"{label} images that arrived as chat files" in rendered

    wrong = [a for a in hashed if f"T+{a} images that arrived as chat files" in rendered]
    assert not wrong, f"a hashed bucket is labelled as chat images: {wrong}"


# ── 3. no superseded accounting may survive a rebuild ──────────────────────

#: Counts from an earlier state of the panel. They are not merely stale, they
#: are wrong, and a reader cannot tell a stale figure from a current one.
SUPERSEDED_COUNTS = ("150", "33", "116")


def test_no_superseded_count_is_rendered(rendered: str) -> None:
    found = [
        n for n in SUPERSEDED_COUNTS if re.search(r"(?<![\d.,])" + n + r"(?![\d.,%])", rendered)
    ]
    assert not found, f"a superseded count is visible on the page: {found}"


# ── 4. claims the evidence does not carry ──────────────────────────────────

#: Phrases that are false as assertions but legitimate — necessary, even — as
#: disclaimers. "not nationally representative" is a thing the page SHOULD say.
NEGATED_OK = ("nationally representative", "national index")

FORBIDDEN_CLAIMS = (
    # the panel is one route, one carrier, one wave — not a national index
    "quality-adjusted airfare price index for india",
    "india's airfare index",
    # nothing is published, and nothing is validated on real longitudinal data
    "validated on real",
    "verified end-to-end",
    "production-ready",
    "mospi validated",
    "endorsed by mospi",
    # no interval exists anywhere
    "confidence interval of",
    "95% ci",
    "margin of error",
    # TPD has no estimator
    "tpd available",
    "tpd result",
)


@pytest.mark.parametrize("claim", FORBIDDEN_CLAIMS)
def test_the_page_makes_no_claim_the_evidence_does_not_carry(rendered: str, claim: str) -> None:
    assert claim not in rendered.lower(), f"unsupported claim on the page: {claim!r}"


@pytest.mark.parametrize("phrase", NEGATED_OK)
def test_scope_phrases_appear_only_as_disclaimers(rendered: str, phrase: str) -> None:
    """These may be denied but never asserted.

    Every occurrence must be negated within the clause, so "not nationally
    representative" passes and "nationally representative panel" does not.
    """
    low = rendered.lower()
    for m in re.finditer(re.escape(phrase), low):
        lead = low[max(0, m.start() - 40) : m.start()]
        assert any(n in lead for n in (" not ", "never ", "no ", "n't ")), (
            f"{phrase!r} is asserted rather than denied, near: "
            f"...{low[max(0, m.start() - 60) : m.end() + 20]}..."
        )


def test_no_untested_cause_is_offered_for_the_observed_difference(rendered: str) -> None:
    """The panel establishes a difference. It does not establish why.

    Caught in review: the page volunteered a return-travel peak as a possible
    cause. Naming a mechanism the data cannot test is storytelling, however
    carefully it is hedged.
    """
    low = rendered.lower()
    for story in ("return-travel peak", "diwali", "holiday demand", "festival demand"):
        assert story not in low, f"an untested cause is offered: {story!r}"
    assert "cause cannot be established from these observations" in low


def test_the_headline_describes_an_engine_not_an_index(rendered: str) -> None:
    """What APIx is today: an auditable measurement engine that publishes nothing."""
    low = rendered.lower()
    assert "auditable airfare measurement engine" in low
    assert "index pending" in low
