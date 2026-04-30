# Third-Party Notices

This file lists third-party services, datasets, fonts, and libraries used by the project.

## Scope

- The project source code authored in this repository is governed by the custom source-available terms in [LICENSE](LICENSE).
- Third-party content remains under its own license and terms.

## Data and Media Sources

1. Wikidata
- Website: https://www.wikidata.org/
- Role: entity metadata and identifiers used in ETL.
- Notes: Wikidata data is generally published under CC0. Verify current terms at source.

2. Wikimedia Commons (via file URLs)
- Website: https://commons.wikimedia.org/
- Role: many flag/media files are resolved to Commons file paths.
- Notes: Each media file can have a different license (for example CC BY-SA, public domain, etc.). License obligations are file-specific.

3. mledoze/countries dataset (local countries.json seed)
- Source repository: https://github.com/mledoze/countries
- Role: base country records for initial population.
- Notes: Use according to the upstream repository license and attribution requirements.

4. flagcdn
- Website: https://flagcdn.com/
- Role: flag image URLs used for base country entries.
- Notes: Treat as third-party hosted assets and follow provider terms and upstream asset licenses.

## Frontend Libraries and Assets

1. Bootstrap
- Website: https://getbootstrap.com/
- License: MIT License

2. Bootstrap Icons
- Website: https://icons.getbootstrap.com/
- License: MIT License

3. Poppins Font
- Source: Google Fonts / Indian Type Foundry
- License: SIL Open Font License 1.1

## Important Compliance Note

If you distribute this project or run a networked modified version, keep this notice file and satisfy all applicable upstream license conditions for third-party assets and data.
