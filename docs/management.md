# Job and application management

Implemented in milestone 3. All endpoints require a session; mutations also
require the custom request header and session-bound CSRF token described in
[security](security.md). User IDs come exclusively from authentication.

## Resources

| Resource | Supported operations |
| --- | --- |
| `/api/v1/companies` | GET paginated/searchable list; POST create |
| `/api/v1/companies/{id}` | GET; PATCH; DELETE if not referenced by a job |
| `/api/v1/jobs` | GET paginated/searchable list; POST create with optional raw description |
| `/api/v1/jobs/{id}` | GET; PATCH; DELETE archives and returns the archived job |
| `/api/v1/jobs/{id}/descriptions` | GET versions newest first; POST append a version |
| `/api/v1/applications` | GET paginated/filterable/sortable list; POST record application |
| `/api/v1/applications/{id}` | GET; PATCH notes and document references |

Job and application results include the company and job details needed by the
frontend. Collection responses use `{items, total, page, page_size}`; page size
is bounded at 100. Default size is 25; the frontend displays 12 records per page.

## Filtering

All three collections accept `q`. Company search uses company name; job search
uses role/company; application search uses role/company/application notes.
Matching is case insensitive, with SQL wildcard characters treated literally.

Jobs support `company_id` and `archived` (false by default). Applications support
`company_id`, `status`, `location`, inclusive `date_from`/`date_to`, and sort:
`newest`, `oldest`, `company`, or `title`. Sorting uses a stable UUID tie-breaker.
Inverted date ranges and unsupported sort values are rejected.

Descriptions are loaded separately rather than sending large raw text in each
listing. The personal-workspace frontend loads reference catalogs for selectors
in pages of 100. At larger scale, replace full selector catalogs with server-side
search/autocomplete; ordinary result lists are already paginated.

## Transactions and preservation

- Job creation and its initial description are one transaction.
- Description changes append immutable versions; the original text, including
  whitespace, is preserved. Identical text reuses the latest version (POST returns 200 for reuse, 201 for creation).
- Partial job edits validate the merged record, so a changed salary maximum
  cannot violate the existing minimum or silently lose currency/period.
- Application creation writes the application and initial applied event in one
  transaction. A failed event insert rolls back the application.
- A job row lock serializes application-attempt allocation and description-version
  allocation. Reapplying creates a distinct incrementing attempt; existing records
  remain unchanged. Concurrent-allocation behavior needs further stress testing.
- Jobs are archived rather than hard deleted. Existing applications stay visible;
  new applications require restoring an archived job first.
- Unknown and foreign-owned resources both return 404, including foreign company
  or job references supplied during creation/update.

Application dates are calendar dates. The initial applied event uses UTC midnight
on that date as an explicit normalization convention, not an observed exact time.
`recorded_at` captures actual insertion time. Analytics must avoid implying
sub-day precision for these application timestamps. Application date editing is
not supported yet because it needs an explicit immutable-history correction policy.

## Frontend

The workspace has Applications, Jobs, Companies, and Documents views; authenticated API
errors handle expired sessions by returning to sign-in. Native dialog forms
provide modal focus behavior, labeled inputs, disabled submission while saving,
and inline error messages. Job screens support archive/restore and versioned
raw-description inspection. Application notes can be edited.

Stage/outcome updates, application timelines, and document references are implemented;
see [history behavior](history.md). Dashboard metrics, extraction, and matching are later milestones.
There are no fabricated status transitions or analytics.

## Verification

PostgreSQL API tests cover ownership, CRUD, partial validation, description
preservation, archive/restore, search/filter/sort/pagination, initial event creation,
and rollback on event failure. Existing authentication/security tests remain intact.
Browser verification used synthetic local data to exercise company/job creation,
application recording, note editing, search, description versions, archive, and restore.

![Application management](screenshots/application-management.jpg)
