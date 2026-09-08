# ai/ — Layer 3

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097)

**Reads the index. Never writes it.**

## Not yet implemented

## The removal test

Delete the Claude API integration and the index must still publish.

## What will live here

LLM narrative explanation of published movements, parser-drift diagnosis, and
schema mapping assistance.

## Parser diagnosis is assisted, never automatic

A site redesign breaking a parser is a high-likelihood risk, and an LLM is
genuinely useful for diagnosing one. But a model proposing a parser change that
silently alters what is collected would change the published numbers from
outside the deterministic path.

Diagnosis is therefore **LLM-assisted with human approval**. The earliest
available signal that a site was redesigned is a rising exclusion rate, which is
published per source and alarmed on — that detection is deterministic and lives
outside this layer.
