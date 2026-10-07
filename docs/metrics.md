# Planned metric definitions

These definitions guide milestone 5. Calculations are not implemented yet.

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
  event counts are a separate series. Use a documented user timezone and
  Monday-based weeks.

An empty denominator produces an unavailable ratio, not a misleading 0%.
Historical conversions remain true after a subsequent rejection or withdrawal.
No-response applications are censored observations; average response time only
summarizes respondents, and must be labeled accordingly.
