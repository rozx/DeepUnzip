# output-localization Specification

## Purpose
Show human output in one of five languages per run, chosen from DEEPUNZIP_LANG or the system language, from a complete message catalog.
## Requirements
### Requirement: Select one output language per run
The system SHALL support five output languages: English (`en`), Simplified Chinese (`zh`), Traditional Chinese (`zh-TW`), Japanese (`ja`) and Korean (`ko`). It SHALL choose one of them at startup:

1. the `DEEPUNZIP_LANG` environment variable, if its value names a supported language;
2. otherwise the system UI language, if it is a supported language;
3. otherwise English.

Language names are matched without regard to case, with `_` and `-` treated alike and any encoding suffix (`.UTF-8`) ignored. Chinese for Taiwan, Hong Kong and Macau, and `zh-Hant`, select Traditional Chinese; any other Chinese selects Simplified Chinese.

All human output of the run SHALL use only the chosen language, including help text.

#### Scenario: Simplified Chinese system
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `zh-CN`
- **THEN** human output SHALL be in Simplified Chinese only

#### Scenario: Traditional Chinese system
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `zh-TW` or `zh-HK`
- **THEN** human output SHALL be in Traditional Chinese only

#### Scenario: Japanese and Korean systems
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `ja-JP` or `ko-KR`
- **THEN** human output SHALL be in Japanese or Korean respectively

#### Scenario: Unsupported system language
- **WHEN** `DEEPUNZIP_LANG` is unset and the system UI language is `fr-FR`
- **THEN** human output SHALL be in English only

#### Scenario: Override
- **WHEN** `DEEPUNZIP_LANG=ja` is set on a Chinese system
- **THEN** human output SHALL be in Japanese only

#### Scenario: Unsupported override value
- **WHEN** `DEEPUNZIP_LANG=fr` is set
- **THEN** the value SHALL be ignored and the system UI language rule SHALL apply

### Requirement: Message catalog with complete coverage
Every user-facing string SHALL come from a message catalog that holds an entry in each of the five languages for every key, with the same placeholders in each. A key missing an entry SHALL fall back to English at runtime, and the test suite SHALL fail when any key lacks any language.

#### Scenario: Catalog completeness check
- **WHEN** a key is added with only English and Simplified Chinese entries
- **THEN** the catalog completeness test SHALL fail

### Requirement: Language-independent machine output
JSON output SHALL contain no catalog text. It SHALL carry only event names, codes and data, so it is identical whatever language is selected.

#### Scenario: JSON under different languages
- **WHEN** the same run is made with `--json` under `DEEPUNZIP_LANG=zh`, `DEEPUNZIP_LANG=ko` and `DEEPUNZIP_LANG=en`
- **THEN** the event streams SHALL be identical apart from timing fields and paths

