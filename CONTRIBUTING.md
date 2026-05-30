# Contributing to SMBD

Thanks for helping build an open, transparent bot-detection tool. The
architecture is designed so the two most common contributions — **new data
sources** and **new detection signals** — are easy and isolated.

## Setup

```bash
pip install -e ".[cli,dev]"
pytest                      # all tests must pass; they run with no creds/keys
```

## Add a detector (a new signal)

1. Create `smbd/detectors/your_signal.py` subclassing
   [`Detector`](smbd/detectors/base.py). Set a unique `name`.
2. Implement `analyze(comments) -> {comment_id: [Signal, ...]}`. Put reusable
   math in `smbd/features/` and call it from the detector.
3. **Emit evidence.** Every `Signal` must carry an `evidence` dict explaining
   *why* it fired — this is non-negotiable; it powers `smbd explain`.
4. **Abstain on missing data.** If the inputs you need aren't present, return
   nothing for that comment. Never guess.
5. Register it in `DEFAULT_DETECTORS` ([`smbd/detectors/__init__.py`](smbd/detectors/__init__.py))
   and add a default weight in [`smbd/config.py`](smbd/config.py).
6. Add tests in `tests/test_detectors.py`: one that fires on a bot fixture, one
   that abstains on the genuine fixture.

## Add a provider (a new data source)

1. Create `smbd/providers/your_source.py` subclassing
   [`Provider`](smbd/providers/base.py).
2. Map the platform payload into the normalized
   [schema](smbd/schema.py) — fill what you can, leave the rest `None`.
3. Network-dependent providers go behind an optional extra in `pyproject.toml`
   and are tested against **recorded fixtures**, not live tokens.

## Ground rules

- **No real user data in the repo.** Fixtures are synthetic only.
- **Outputs are probabilistic.** Keep language as "signals/likelihood/confidence",
  never definitive accusations.
- **Respect platform terms.** Official adapters must only access data the user
  is authorized for. Scraping lives in an opt-in extra with clear warnings.
- Keep the **core dependency-free**; heavy deps (ML, graph libs, vendor SDKs)
  go behind extras.
