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

- `.github/workflows/publish.yml` triggers on a published GitHub Release
  (routes to the `pypi` job only) or manual `workflow_dispatch` (routes to
  either `testpypi` or `pypi`, `testpypi` by default). It has no
  `push`/`pull_request` trigger.
- `ci.yml` runs on push/PR and validates the test suite; it does not
  publish anywhere.
- Before the first release, complete the one-time setup: create the GitHub
  `pypi` and `testpypi` Environments (with a required reviewer on `pypi`)
  and register a Trusted Publisher on pypi.org and test.pypi.org for this
  repository, `publish.yml`, and the matching environment. Until then both
  publish jobs will fail authentication, which is expected.
- Check https://pypi.org/project/aei-link-clearance/ directly for the
  current release state rather than trusting this file to stay up to date.
