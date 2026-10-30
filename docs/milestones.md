# Implementation milestones

1. Foundation: schema, migration, configuration, Docker, health, frontend shell,
   tests, documentation, CI. Implemented; Docker execution verified locally on October 7, 2026.
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
   Implemented with date filters, timezone-aware activity, empty states, and tested
   historical conversions.
6. Extraction: deterministic provider, validated structured output, evidence,
   immutable analysis versions and parser tests. Implemented with source spans,
   authenticated APIs, version review, and conservative rule-based extraction.
7. Matching: editable profile, weighted evidence, missing-data handling,
   persisted score explanations and tests. Implemented for classified skill
   evidence, projects, and experience; education and duration need manual review.
8. Release: end-to-end checks, accessibility, production deployment, screenshots,
   operational documentation. Local API smoke and release configuration implemented;
   Docker build/startup, container tests, static proxy, and synthetic restore
   rehearsal verified. Public HTTPS deployment and secure-cookie smoke checks verified on October 30,
   2026. Broader accessibility and public account-recovery work remain pending.

The usable MVP ends at milestone 5; the portfolio release includes 6–8.
Defer uploads, scraping, email/calendar integrations, embeddings, LLM providers,
notifications, queues, and role-category classification.
