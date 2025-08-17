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

## [0.2.1]

### Changed

- Simplified signal handling in `@async_receiver` decorator by removing redundant iterable checking, as `django.dispatch.receiver` already handles multiple signals internally.

## [0.2.0]

### Added

- Support for async signal handlers - async functions decorated with `@async_receiver` are now properly handled using `asgiref.sync.async_to_sync` for execution in Django Q2's worker processes.

## [0.1.0]

### Added

- Created `@async_receiver` decorator for processing Django signals asynchronously through Django Q2.
  - Includes automatic serialization and reconstruction of model instances for task queue compatibility.
  - Handles deleted instances with `_instance_pk` preservation.
  - Full compatibility with Django's `@receiver` decorator options.

### New Contributors

- Josh Thomas <josh@joshthomas.dev> (maintainer)

[unreleased]: https://github.com/joshuadavidthomas/django-q-signals/compare/v0.2.1...HEAD
[0.1.0]: https://github.com/joshuadavidthomas/django-q-signals/releases/tag/v0.1.0
[0.2.0]: https://github.com/joshuadavidthomas/django-q-signals/releases/tag/v0.2.0
[0.2.1]: https://github.com/joshuadavidthomas/django-q-signals/releases/tag/v0.2.1
