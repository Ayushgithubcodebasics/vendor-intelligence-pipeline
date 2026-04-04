# GDPR Compliance Statement

## Data classification

The dataset used in this project contains business transaction records: purchase orders,
sales receipts, inventory counts, and vendor invoice data for an unnamed retail distribution
company operating across approximately 80 store locations.

This dataset contains **no personal data** as defined under GDPR Article 4(1). It includes no
names of natural persons, no email addresses, no national identification numbers, no device
identifiers, no location data attributable to an individual, and no special-category personal
data under GDPR Article 9. The identifiers present in the dataset (`VendorNumber`, `Store`,
`Brand`, `PONumber`) refer to legal entities, physical retail locations, or product codes.

## Data provenance

The dataset exhibits characteristics consistent with synthetic or anonymised business data.
Geographic names do not correspond to real jurisdictions, transaction relationships are highly
arithmetically consistent, and no personally identifiable information appears in any source file.

This project was prepared for portfolio and educational purposes only. No attempt has been made
to reverse-engineer, re-identify, or otherwise infer the identity of any natural person.

## Data retention and publication policy

The full raw CSV package is retained locally for reproducible pipeline execution but is **not
required for public review**. The public/shareable version of this project should expose only:

- the 5,000-row quickstart samples in `data/sample/`
- derived analytical outputs in `outputs/`
- code, tests, and documentation

If any future extension of this project were to incorporate individual-level customer or employee
data, a GDPR Data Protection Impact Assessment (DPIA) and documented technical and organisational
controls would be required before processing.

## Legal basis note

This project does not process personal data and therefore does not require a legal basis under
GDPR Article 6. This statement is included as a matter of professional transparency and European
data-governance best practice.
