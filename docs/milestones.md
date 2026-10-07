# Implementation milestones

1. Foundation: schema, migration, configuration, Docker, health, frontend shell,
   tests, documentation, CI. Implemented; Docker execution not verified locally.
2. Authentication: password hashing, secure sessions, CSRF, account ownership,
   user isolation tests. Implemented, including browser verification of registration,
   sign-in, reload restoration, and sign-out. Shared production rate limiting,
   email verification, and password recovery remain release work.
3. Management: companies, jobs, descriptions, applications, React forms,
   search/filter/sort/pagination. Implemented and browser verified. Initial applied
   events are transactional.
4. History: transactional events and current-state changes, concurrency behavior,
   timeline, document metadata. Implemented and browser verified. PostgreSQL tests
   cover concurrent transitions, rollback, ownership, and immutable history.
5. Dashboard: metrics, cohort/activity handling, status counts, useful charts.
6. Extraction: deterministic provider, validated structured output, evidence,
   immutable analysis versions and parser tests.
7. Matching: editable profile, weighted evidence, missing-data handling,
   persisted score explanations and tests.
8. Release: end-to-end checks, accessibility, production deployment, screenshots,
   operational documentation.

The usable MVP ends at milestone 5; the portfolio release includes 6–8.
Defer uploads, scraping, email/calendar integrations, embeddings, LLM providers,
notifications, queues, and role-category classification.
