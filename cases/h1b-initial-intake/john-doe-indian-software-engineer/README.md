# John Doe — Initial H-1B Intake Test Case

**Fictional / synthetic / not valid for any real immigration filing.**

This case is designed to test LEI at the **initial H-1B intake** stage, before the legal team has prepared the LCA, Form I-129, or employer support letter.

## Case ID

`john-doe-indian-software-engineer-initial-intake`

## LEI Display ID

`LEI_CASE_001_JOHN_DOE`

## Workflow Stage

`initial_intake`

## Scenario

John Doe is an Indian software engineer currently working for Northstar Data Systems, Inc. in F-1 STEM OPT status. HR wants legal to prepare an H-1B cap change-of-status petition with an intended October 1, 2026 start date.

## Intended Upload Folder

Upload only:

`packet-for-lei-upload/`

Do **not** upload:

`attorney-only/`, `ground-truth.json`, or `case.json`

## Why This Case Exists

Existing synthetic H-1B packets often include legal-team-created documents like a certified LCA and employer support letter. This case tests whether LEI understands a more realistic intake-stage packet where HR and the foreign national provide raw source documents, and the legal team later creates the filing documents.

## Documents Included

### HR-provided documents

- HR intake questionnaire
- Offer letter
- Job description
- Company profile
- Org chart text version
- Remote work policy excerpt
- Compensation confirmation

### Foreign-national-provided documents

- Beneficiary intake questionnaire
- Resume
- Fictional passport data page specimen
- I-94/status summary
- Fictional STEM OPT EAD specimen
- Paystub summary
- Travel history summary
- Address history summary
- Fictional degree verification specimen

The passport, STEM OPT EAD, and degree verification files are visual specimens mixed into the foreign-national-provided documents folder. They are intentionally marked **SPECIMEN / FICTIONAL TEST DOCUMENT / NOT VALID**.

## Expected Legal Issues / Test Findings

A strong LEI review should identify:

1. Certified LCA is absent because legal would create it; this should not be treated as an intake defect.
2. Employer support letter is absent because legal would create it; this should not be treated as an intake defect.
3. Passport expires shortly after requested H-1B start date; this is a beneficiary follow-up/travel-I-94 advisory, not automatically a filing blocker.
4. Hybrid remote work from Athens, GA requires LCA/worksite analysis.
5. Current title differs from proposed H-1B title, but a title difference alone is not automatically material.
6. Computer Science degrees appear related to the Software Engineer I role.
7. Salary requires prevailing wage/LCA review, but LEI should not conclude it is below wage without SOC, wage level, worksite, and wage data.
8. John Doe vs. John A. Doe is a name-formatting follow-up, not a serious identity mismatch without more.

See `ground-truth.json` for the attorney-only answer key.
