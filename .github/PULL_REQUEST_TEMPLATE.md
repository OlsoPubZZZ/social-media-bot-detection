<!-- Thanks for contributing to SMBD! -->

## What & why

<!-- What does this change, and what problem does it solve? -->

## Type of change

- [ ] New detector (signal)
- [ ] New provider (data source)
- [ ] Bug fix
- [ ] Scoring / reporting change
- [ ] Docs
- [ ] Other

## Checklist

- [ ] `pytest -q` passes locally (offline — no creds/keys needed).
- [ ] New detectors **emit evidence** and **abstain on missing data** (see [CONTRIBUTING.md](../CONTRIBUTING.md)).
- [ ] New network providers are tested against **recorded fixtures**, not live tokens, and live deps sit behind an optional extra.
- [ ] No real user data, API keys, or secrets in the diff or fixtures.
- [ ] Outputs use "signals / likelihood / confidence" language — never definitive accusations.
- [ ] Docs / CHANGELOG updated if behavior or config changed.
