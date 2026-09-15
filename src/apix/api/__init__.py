"""The APIx API for statistical consumers -- PS 26056 requirement 6D.

Standard-library HTTP, JSON responses, every payload wrapped with its
methodology version, output class and publication state. See
``apix.api.server`` for endpoints and ``apix.api.payloads`` for what each
returns. ``python -m apix.api`` starts it.
"""

from apix.api.server import DEFAULT_PORT, ENDPOINTS, route, serve

__all__ = ["DEFAULT_PORT", "ENDPOINTS", "route", "serve"]
