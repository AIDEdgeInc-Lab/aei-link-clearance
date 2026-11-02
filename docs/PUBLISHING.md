# Publishing process

This document describes how `aei-link-clearance` is published to PyPI,
mirrored from `aei-link-clearance`'s and `aei-geo-features`'
publishing setup.

## How a release would be published

- **Normal path**: a maintainer publishes a GitHub Release. This fires
  the workflow's `release: published` trigger, which builds the wheel/
  sdist and publishes them to production PyPI (`environment: pypi`).
- **Manual path**: the workflow can also be run manually via
  `workflow_dispatch` with a `target` input of `testpypi` (default) or
  `pypi`. A manual run always requires `target` to be chosen explicitly;
  `pypi` is never the default.

Both paths run through the same `build` job first, and both publish
jobs are mutually exclusive - only one of `publish-testpypi` /
`publish-pypi` ever runs for a given trigger.

## Why Trusted Publishing instead of a token

PyPI Trusted Publishing lets a specific GitHub Actions workflow
(identified by repo, workflow filename, and environment) request a
short-lived upload credential directly from PyPI via OpenID Connect (OIDC)
at publish time. There is no long-lived `PYPI_API_TOKEN` secret to create,
rotate, store in GitHub Secrets, or accidentally leak in a log.

## Trusted Publisher registration

Must be registered as a Trusted Publisher on both pypi.org and
test.pypi.org, tied to this repository, the `publish.yml` workflow
filename, and the `pypi`/`testpypi` environments respectively. That
registration happens on PyPI's own site (Account Settings -> Publishing),
not in this repository - there is nothing to configure here beyond the
workflow file itself, and it must be done by a human with access to the
relevant PyPI account. The `pypi` GitHub Environment additionally has a
required reviewer configured with admin-bypass disabled, so a production
deployment always pauses for manual approval in the Actions UI regardless
of what triggered it.

## Current state

Updated 2026-11-01 from the repository and PyPI, not from memory:

- `.github/workflows/publish.yml` triggers on a published GitHub Release (routes to the `pypi` job only) or manual `workflow_dispatch`
  (routes to either `testpypi` or `pypi`, `testpypi` by default). It has no `push`/`pull_request` trigger.
- **PyPI (pypi.org): the Trusted Publisher is registered and in use.** Releases 0.1.0, 0.2.0 and 0.2.1 were each published by a run of
  this workflow (`release` event, environment `pypi`), and PyPI holds the attestations for them. No token is used.
- **test.pypi.org:** whether a Trusted Publisher is registered there was not checked; the `testpypi` job has not been used for a release.
- **GitHub Environments:** `pypi` has a required reviewer, so a production deployment pauses for approval in the Actions UI; `testpypi`
  has no protection rule.
- `ci.yml` runs on push/PR and validates the test suite; it does not publish anywhere.
- To release: merge to `main`, create the tag `vX.Y.Z` on it, publish a GitHub Release for that tag, approve the `pypi` deployment, then check
  `pip index versions aei-link-clearance`.
- Check https://pypi.org/project/aei-link-clearance/ directly for the current release state rather than trusting this file to stay up to date.
