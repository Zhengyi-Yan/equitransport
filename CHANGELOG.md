# Changelog

All notable changes to this project are documented here.

This project follows semantic versioning: `MAJOR.MINOR.PATCH`.

- `MAJOR` changes are for incompatible API changes.
- `MINOR` changes are for new backwards-compatible functionality.
- `PATCH` changes are for backwards-compatible fixes, documentation updates,
  metadata updates, and test improvements.

## [0.1.5] - 2026-06-05

### Added

- Added Quarto website documentation with a usage guide, API reference, and
  data/methods page.
- Added coverage configuration and expanded pytest coverage for access,
  equity, data-loading, plotting, and validation paths.
- Added an MIT `LICENSE` file.
- Added this changelog.

### Changed

- Updated package version metadata from `0.1.0` to `0.1.5`.
- Updated GitHub Actions test dependencies so CI can run coverage checks.
- Expanded README installation, documentation, expected-output, and licensing
  guidance.
- Expanded public function docstrings and plotting type hints.

## [0.1.0] - 2026-05-22

### Added

- Initial TestPyPI release.
- Core Auckland transport equity workflow:
  - NZDep aggregation from SA1 to SA2.
  - Public transport stop access calculation.
  - NZDep quintile equity summary and Gini coefficient.
  - Static map and bar-chart plotting helpers.
