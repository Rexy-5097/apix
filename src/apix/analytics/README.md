# analytics/ — Layer 3

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097)

**Reads the index. Never writes it.**

## Not yet implemented

No anomaly detection, forecasting or shock detection has been written.

## The removal test

Delete this directory entirely and the index must still publish. Collection,
cleaning, deduplication, Jevons, Young/Modified Laspeyres, TPD and index
publication must all continue to work. If they do not, the layer boundary has
been violated somewhere — and `tests/test_architecture.py` will say where.

## What will live here

Anomaly detection (Isolation Forest), 30-day nowcast forecasting (LightGBM),
change-point shock detection (`ruptures`), and operational source-health scoring.

These libraries are exactly the ones the statistics layer may not import. That
is the point of the split: they are welcome here and forbidden there.

## Model-based imputation belongs here, not in the index path

Temporal matrix factorisation and similar completion methods are fitted,
stochastic procedures. They belong here as a **candidate improvement evaluated
against the deterministic rule**, never embedded in the index path where they
would quietly break the reproducibility guarantee.

The deterministic rule they are measured against: a missing cell inherits the
price relative of its parent stratum where one is available; where none is, the
cell is suppressed and the coverage loss is published.
