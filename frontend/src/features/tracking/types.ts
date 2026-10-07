export interface Company {
  id: string;
  name: string;
  website: string | null;
  location: string | null;
  notes: string | null;
}
export interface Job {
  id: string;
  company_id: string;
  company: Company;
  title: string;
  url: string | null;
  location: string | null;
  work_arrangement: string | null;
  employment_type: string | null;
  salary_min: string | null;
  salary_max: string | null;
  salary_currency: string | null;
  salary_period: string | null;
  posted_on: string | null;
  deadline_on: string | null;
  archived_at: string | null;
}
export interface Application {
  resume_id: string | null;
  cover_letter_id: string | null;
  id: string;
  job: Job;
  applied_on: string;
  attempt_number: number;
  current_stage: string;
  status: string;
  notes: string | null;
}
export interface Description {
  id: string;
  raw_text: string;
  version: number;
  created_at: string;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export const label = (value: string | null) =>
  value ? value.replaceAll('_', ' ') : 'Not specified';
export const localDate = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

export interface DocumentVersion {
  id: string;
  kind: 'resume' | 'cover_letter';
  label: string;
  version_label: string | null;
  storage_reference: string | null;
  archived_at: string | null;
}
export interface ApplicationEvent {
  id: string;
  application_id: string;
  event_type: string;
  occurred_at: string;
  recorded_at: string;
  notes: string | null;
}
