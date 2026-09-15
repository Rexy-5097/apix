"""Versioned configuration: advance-purchase windows and the route basket.

Configuration, not methodology. Every value here is declared, versioned and
carries its provenance, so the question *"where did this number come from?"* has
an answer that is not "someone typed it".

Two things this package exists to keep apart:

* **The frozen APIx production APW vector** (spec A.3, LOCKED) and **the window
  set PS 26056 asks for**. They differ, and neither is silently rewritten to
  match the other -- see :mod:`apix.config.apw`.
* **Provisional route weights** and **official DGCA-derived weights**. The
  basket carries a ``status`` that says which it is holding, and nothing may
  present a provisional weight as an official one -- see
  :mod:`apix.config.basket`.
"""

from apix.config.apw import (
    APIX_FROZEN_WINDOWS,
    PS_26056_WINDOWS,
    ApwWindowSet,
    window_set,
)
from apix.config.basket import (
    DEMO_BASKET,
    PILOT_BASKET,
    BasketStatus,
    RouteBasket,
    RouteWeight,
)

__all__ = [
    "APIX_FROZEN_WINDOWS",
    "DEMO_BASKET",
    "PILOT_BASKET",
    "PS_26056_WINDOWS",
    "ApwWindowSet",
    "BasketStatus",
    "RouteBasket",
    "RouteWeight",
    "window_set",
]
