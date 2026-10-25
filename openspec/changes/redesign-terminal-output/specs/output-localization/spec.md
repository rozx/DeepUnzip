## ADDED Requirements

### Requirement: Select one output language per run
The system SHALL choose a single output language at startup:

1. `zh` or `en` from the `DEEPUNZIP_LANG` environment variable, if set to one of those values;
2. otherwise Chinese if the system UI language is any `zh*` locale;
3. otherwise English.

All human output of the run SHALL use only the chosen language, including help text.

#### Scenario: Chinese system
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `zh-CN`
- **THEN** human output SHALL be in Chinese only

#### Scenario: English system
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `en-US`
- **THEN** human output SHALL be in English only

#### Scenario: Override
- **WHEN** `DEEPUNZIP_LANG=en` is set on a Chinese system
- **THEN** human output SHALL be in English only

#### Scenario: Unsupported override value
- **WHEN** `DEEPUNZIP_LANG=fr` is set
- **THEN** the value SHALL be ignored and the system UI language rule SHALL apply

### Requirement: Message catalog with complete coverage
Every user-facing string SHALL come from a message catalog that holds an English and a Chinese entry for each key. A key missing its Chinese entry SHALL fall back to English at runtime, and the test suite SHALL fail when any key lacks either language.

#### Scenario: Catalog completeness check
- **WHEN** a key is added with only an English entry
- **THEN** the catalog completeness test SHALL fail

### Requirement: Language-independent machine output
JSON output SHALL contain no catalog text. It SHALL carry only event names, codes and data, so it is identical whatever language is selected.

#### Scenario: JSON under both languages
- **WHEN** the same run is made with `--json` under `DEEPUNZIP_LANG=zh` and `DEEPUNZIP_LANG=en`
- **THEN** the two event streams SHALL be identical apart from timing fields
