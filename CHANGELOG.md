# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project attempts to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
## [${version}]
### Added - for new features
### Changed - for changes in existing functionality
### Deprecated - for soon-to-be removed features
### Removed - for now removed features
### Fixed - for any bug fixes
### Security - in case of vulnerabilities
[${version}]: https://github.com/joshuadavidthomas/django-q-signals/releases/tag/v${version}
-->

## [Unreleased]

- Created `@async_receiver` decorator for processing Django signals asynchronously through Django Q2.
  - Includes automatic serialization and reconstruction of model instances for task queue compatibility.
  - Handles deleted instances with `_instance_pk` preservation.
  - Full compatibility with Django's `@receiver` decorator options.

### New Contributors

- Josh Thomas <josh@joshthomas.dev> (maintainer)

[unreleased]: https://github.com/joshuadavidthomas/django-q-signals/tree/main
