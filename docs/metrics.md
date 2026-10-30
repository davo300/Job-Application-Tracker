# Dashboard metric definitions

Implemented in milestone 5 at `GET /api/v1/analytics/dashboard`. All queries are
scoped to the authenticated account. Optional inclusive `date_from` and `date_to`
filters select cohorts and activity independently; reversed ranges are rejected.

Funnels use cohorts selected by application date. Activity uses event occurrence
date. Count distinct applications, never the number of repeated events.

- Response: first assessment, interview, offer, or rejection event. Exclude notes,
  applied events, and withdrawal. Response rate divides responding applications
  by submitted applications in the selected cohort.
- Assessment conversion: applications with an assessment event / cohort size.
- Interview conversion: applications with any interview event / cohort size.
- Interview-to-offer: interviewed applications with offer events / interviewed
  applications. A direct offer without an interview does not enter this ratio.
- Time to response: elapsed time from the initial applied event to the first
  qualifying response. Show unanswered count; do not treat unanswered as zero.
- Stage duration: elapsed time between consecutive stage transitions. Exclude
  note events; account for skipped and repeated stages explicitly.
- Weekly activity: application counts grouped by application calendar dates;
  event counts are a separate series, excluding initial applied events but including
  notes and repeated transitions. The browser supplies its IANA timezone; the API
  defaults to UTC and validates timezone names. Weeks begin Monday.

An empty denominator produces an unavailable ratio, not a misleading 0%.
Historical conversions remain true after a subsequent rejection or withdrawal.
No-response applications are censored observations; average response time only
summarizes respondents, and must be labeled accordingly.

Current status counts describe the selected cohort now; active-stage counts exclude
closed applications. Offer conversion counts distinct applications with offer events
over cohort size. Completed stage durations include repeated-stage intervals and
end at the next stage or outcome. Notes are ignored, skipped stages have no interval,
and open intervals are excluded.

Time to response uses UTC midnight on the application calendar date, so it is
approximate to that day. Weekly activity only returns weeks with activity. Date
filters do not truncate a cohort application's later history.

The API uses one ownership-scoped joined statement for a consistent snapshot, then
calculates metrics in Python. This suits a personal tracker; large histories will
need SQL aggregation or a bounded reporting strategy before broader scale.

Verification includes empty denominators, repeated interviews, direct offers,
terminal-state history, unanswered applications, timezone boundaries, independent
activity/cohort filters, authentication, account isolation, and invalid filters.
