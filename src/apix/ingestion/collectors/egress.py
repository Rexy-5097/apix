"""The declared egress policy — PS 26056 requirement 4, "IP rotation".

The problem statement lists IP rotation among the things a scraper must
*handle*, in the same sentence that requires compliance with each source's
terms. Rotation is a neutral infrastructure technique; what decides its
character is **purpose**, and purpose is legible from design:

* rotating for geographic distribution, redundancy or load spreading is
  operational;
* rotating **in response to a block, a challenge or an HTTP 429** is evasion,
  whatever it is called.

APIx's policy is stricter than the compliance minimum, and for a statistical
reason rather than a legal one. Airline pricing can vary by detected point of
sale, so an index whose egress wanders is an index whose sampling frame wanders
-- a non-price effect the methodology cannot remove. **We would refuse to rotate
even if every source permitted it.**

So the policy is: one stable, declared, attributable egress; rotation never;
and -- the property a test can check -- **no code path from a refusal signal to
egress selection**. :func:`select_egress` takes no outcome, no page state and no
status code, by construction. ``tests/test_egress_policy.py`` walks every
function in ``src/apix/`` and fails the build if one both handles a refusal and
touches egress selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EgressMode(Enum):
    #: One declared egress for the whole collection identity.
    SINGLE_STABLE = "SINGLE_STABLE"


class RotationPolicy(Enum):
    #: The only value APIx declares. Kept as an enum so the *absence* of the
    #: other values is a decision on record, not an omission.
    NEVER = "NEVER"


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    """What egress the collector uses, and what it will never do with it."""

    policy_id: str
    version: str
    mode: EgressMode
    rotation: RotationPolicy
    #: The label recorded on every attempt so a source can attribute traffic.
    egress_label: str
    #: An identifying User-Agent naming the project is sent on every request.
    identifying_user_agent: bool
    #: Always False. Present as a field so a test can assert it, not so it can be set.
    rotate_on_refusal: bool
    authority: str

    def __post_init__(self) -> None:
        if self.rotate_on_refusal:
            raise ValueError(
                "rotate_on_refusal must be False. Rotating in response to a block, challenge "
                "or 429 is evasion, and the acquisition resolution excludes it."
            )
        if self.rotation is not RotationPolicy.NEVER:
            raise ValueError("APIx declares exactly one rotation policy: NEVER")
        if not self.identifying_user_agent:
            raise ValueError("every request must identify the project (protocol s12)")

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "mode": self.mode.value,
            "rotation": self.rotation.value,
            "egress_label": self.egress_label,
            "identifying_user_agent": self.identifying_user_agent,
            "rotate_on_refusal": self.rotate_on_refusal,
            "authority": self.authority,
        }


#: The one declared policy. Changing it is a reviewed change to this file.
DECLARED_EGRESS = EgressPolicy(
    policy_id="apix-egress",
    version="1.0",
    mode=EgressMode.SINGLE_STABLE,
    rotation=RotationPolicy.NEVER,
    egress_label="apix-collector-primary",
    identifying_user_agent=True,
    rotate_on_refusal=False,
    authority=(
        "APIx Acquisition Strategy -- Final Resolution, s05 and s12; "
        "compliance/collection-control-contract.md C-0; dossier s05"
    ),
)


def select_egress(policy: EgressPolicy = DECLARED_EGRESS) -> str:
    """The egress to use for a request.

    Deliberately takes **no** outcome, page state, HTTP status or attempt
    history. There is one answer and nothing about a refusal can change it.
    That signature is the architectural guarantee; see the test.
    """
    return policy.egress_label


__all__ = ["DECLARED_EGRESS", "EgressMode", "EgressPolicy", "RotationPolicy", "select_egress"]
