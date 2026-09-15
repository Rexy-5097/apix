"""IndiGo NDC: what is confirmed, what is not, and credential handling.

**Request model: UNCONFIRMED.** On 2026-09-15 every page of IndiGo's developer
portal (developer.goindigo.in) returned HTTP 502 from the portal gateway. What
is known comes only from search-engine extracts of that portal [INDEX]:

* shopping is an ``IATA_AirShoppingRQ`` answered by a Navitaire NDC Gateway with
  an ``IATA_AirShoppingRS``;
* developers "sign up to get API keys";
* generating an NDC token takes a *subscription key* and an *authorization key*.

Unknown, and therefore NOT implemented: the UAT and production base URLs, the
token endpoint and header names, the NDC schema version, JSON vs XML payloads,
whether ``OfferPrice`` or ``ServiceList`` is needed for the final total and
baggage, fare-brand representation, and any rate or look-to-book limits. No
request builder, parser or fixture exists, because each would have to invent
those details. See ``docs/engineering/indigo-ndc.md``.

What this module does provide is independent of all of that:

* credentials are read from the environment only, validated, and never printed;
* the environment variable names follow the two keys the portal names, and are
  PROVISIONAL until the authentication page can be read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

#: The official request/response model has not been confirmed from IndiGo documentation.
NDC_REQUEST_MODEL_STATUS = "UNCONFIRMED"
#: Why, for display. Kept in one place so the CLI and docs cannot drift.
NDC_BLOCKER = (
    "the IndiGo NDC request/response model is UNCONFIRMED: developer.goindigo.in returned "
    "HTTP 502 on every page on 2026-09-15, so the UAT URL, token flow, NDC version and "
    "AirShopping payload could not be read from official documentation. No request was sent"
)

ENV_BASE_URL = "INDIGO_NDC_BASE_URL"
ENV_SUBSCRIPTION_KEY = "INDIGO_NDC_SUBSCRIPTION_KEY"
ENV_AUTHORIZATION_KEY = "INDIGO_NDC_AUTHORIZATION_KEY"
REQUIRED_ENV: tuple[str, ...] = (ENV_BASE_URL, ENV_SUBSCRIPTION_KEY, ENV_AUTHORIZATION_KEY)

REDACTED = "<redacted>"


class CredentialError(ValueError):
    """Credentials are missing or malformed. The message never contains a secret."""


def credentials_present(environ: Mapping[str, str]) -> bool:
    """Whether every required variable is set to a non-empty value."""
    return all((environ.get(name) or "").strip() for name in REQUIRED_ENV)


@dataclass(frozen=True, slots=True, repr=False)
class NdcCredentials:
    base_url: str
    subscription_key: str = field(repr=False)
    authorization_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise CredentialError(f"{ENV_BASE_URL} must be an https:// URL")
        for name, value in (
            (ENV_SUBSCRIPTION_KEY, self.subscription_key),
            (ENV_AUTHORIZATION_KEY, self.authorization_key),
        ):
            if not value or value != value.strip() or any(ch.isspace() for ch in value):
                raise CredentialError(f"{name} is empty or contains whitespace")

    def __repr__(self) -> str:
        return (
            f"NdcCredentials(base_url={self.base_url!r}, "
            f"subscription_key={REDACTED}, authorization_key={REDACTED})"
        )

    __str__ = __repr__

    def redact(self, text: str) -> str:
        """Remove both keys from any text before it is logged or stored."""
        for secret in (self.subscription_key, self.authorization_key):
            text = text.replace(secret, REDACTED)
        return text

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> NdcCredentials:
        missing = [name for name in REQUIRED_ENV if not (environ.get(name) or "").strip()]
        if missing:
            raise CredentialError(f"missing environment variables: {missing}")
        return cls(
            base_url=environ[ENV_BASE_URL].strip(),
            subscription_key=environ[ENV_SUBSCRIPTION_KEY],
            authorization_key=environ[ENV_AUTHORIZATION_KEY],
        )


__all__ = [
    "ENV_AUTHORIZATION_KEY",
    "ENV_BASE_URL",
    "ENV_SUBSCRIPTION_KEY",
    "NDC_BLOCKER",
    "NDC_REQUEST_MODEL_STATUS",
    "REDACTED",
    "REQUIRED_ENV",
    "CredentialError",
    "NdcCredentials",
    "credentials_present",
]
