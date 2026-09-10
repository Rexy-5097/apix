"""The version vector — spec O.

Carried on every published output. For APIx-L, ``model_version`` is N/A: an
APIx-L output carrying a non-null ``model_version`` means a fitted model has
entered the deterministic path, and it is a **defect**, not a field value.
"""

from __future__ import annotations

from dataclasses import dataclass

from apix.schemas.enums import Tier

MODEL_VERSION_NOT_APPLICABLE = "N/A"


@dataclass(frozen=True, slots=True)
class VersionVector:
    """Identifies a computation exactly — spec O.1.

    Spec P.1 guarantees that the same
    ``(data_snapshot_id, methodology_version, basket_version, weight_version,
    code_version)`` produces a bit-identical APIx-L result. Those five fields are
    the reproducibility tuple; ``parser_version`` identifies the extraction that
    produced the observations, and ``tier`` is recorded per cell.

    ``source_precedence`` was added by methodology v2.1 §O: it identifies the
    ordered source list in force (§D.8), whose
    :attr:`~apix.statistics.elementary.sources.SourcePrecedence.version` selects
    which quote each matched pair is priced from. It is optional on this
    dataclass so that unit fixtures need not carry it, and **required by the
    publication entry point** :func:`~apix.statistics.index.publication.publish`,
    because §O.1 carries it on every published output.

    It is deliberately **not** part of :meth:`reproducibility_tuple`: spec P is
    UNCHANGED in v2.1 and names five fields. That leaves a gap — two runs whose
    precedence lists differ can price the same snapshot differently while
    claiming the same reproducibility tuple — which is registered as **AMB-10**
    rather than closed here by widening a LOCKED rule.
    """

    data_snapshot_id: str
    methodology_version: str
    basket_version: str
    weight_version: str
    parser_version: str
    code_version: str
    model_version: str | None = None
    tier: Tier | None = None
    source_precedence: str | None = None

    def __post_init__(self) -> None:
        required = {
            "data_snapshot_id": self.data_snapshot_id,
            "methodology_version": self.methodology_version,
            "basket_version": self.basket_version,
            "weight_version": self.weight_version,
            "parser_version": self.parser_version,
            "code_version": self.code_version,
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise ValueError(f"version vector is missing required fields: {missing}")

    @property
    def is_deterministic_path(self) -> bool:
        """True when no fitted model contributed — spec O.1, INV-12.

        ``None`` and the literal ``"N/A"`` both mean "no model". Anything else is
        a model version, and an APIx-L output must not carry one.
        """
        return self.model_version in (None, MODEL_VERSION_NOT_APPLICABLE)

    def assert_apix_l_safe(self) -> None:
        """Raise if a model version has leaked into the deterministic path.

        Called by the APIx-L entry point before it returns. This is the
        load-bearing assertion of spec O.1, enforced rather than documented.
        """
        if not self.is_deterministic_path:
            raise ValueError(
                f"APIx-L version vector carries model_version={self.model_version!r}. "
                "For APIx-L, model_version must be N/A (spec O.1, INV-12): a "
                "non-null value means a fitted model entered the deterministic path."
            )

    def reproducibility_tuple(self) -> tuple[str, str, str, str, str]:
        """The five fields spec P.1 guarantees bit-identical output for."""
        return (
            self.data_snapshot_id,
            self.methodology_version,
            self.basket_version,
            self.weight_version,
            self.code_version,
        )

    def render(self) -> str:
        """Human-readable rendering — spec O.2."""
        tier = "-" if self.tier is None else str(self.tier.value)
        model = self.model_version or MODEL_VERSION_NOT_APPLICABLE
        return (
            f"snapshot {self.data_snapshot_id} · methodology {self.methodology_version} · "
            f"basket {self.basket_version} · weight {self.weight_version} · "
            f"parser {self.parser_version} · model {model} · "
            f"code {self.code_version} · tier {tier}"
        )
