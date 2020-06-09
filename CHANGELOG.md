# Changelog
Development of this bot is quite chaotic. This document will try to document
the biggest changes, most importantly those that need some kind of edits to
configuration or database.

## [Unreleased]
### Added
- Chameleon cog (deprecating some of the code in `features/reaction.py`)

### Maintenance
You need to update the database table `subjects`:

```sql
ALTER TABLE subjects
ADD COLUMN category VARCHAR,
ADD COLUMN name VARCHAR;
```


## [0.1.0]
Rubbergoddess detached from its parent project - [Rubbergod](https://github.com/Toaster192/rubbergod).

[Unreleased]: https://github.com/sinus-x/rubbergoddess/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sinus-x/rubbergoddess/releases/tag/v0.1.0