export type UserRole = 'Admin' | 'Radiologist' | 'ReferringClinician';

export interface Token {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export type AdministrativeGender = 'male' | 'female' | 'other' | 'unknown';

export interface Patient {
  id: string;
  mrn: string;
  family_name: string;
  given_name: string;
  birth_date: string | null;
  sex: AdministrativeGender;
  phone: string | null;
  consent_acknowledged: boolean;
  consent_acknowledged_at: string | null;
  extra: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

export interface PatientCreate {
  mrn: string;
  family_name: string;
  given_name: string;
  birth_date?: string | null;
  sex: AdministrativeGender;
  phone?: string | null;
  consent_acknowledged: boolean;
}

export type StudyStatus =
  | 'Uploading'
  | 'Processing'
  | 'Pending'
  | 'InReview'
  | 'Reported'
  | 'Failed';

export interface Study {
  id: string;
  encounter_id: string;
  patient_id: string;
  status: StudyStatus;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  is_dicom: boolean;
  has_preview: boolean;
  modality: string | null;
  study_date: string | null;
  body_part: string | null;
  accession_number: string | null;
  processing_error: string | null;
  created_at: string;
}

export interface UploadSession {
  id: string;
  encounter_id: string;
  filename: string;
  total_size: number;
  received_bytes: number;
  status: string;
}

export type ReportStatus = 'Draft' | 'Final';

export interface Report {
  id: string;
  study_id: string;
  patient_id: string;
  author_id: string | null;
  status: ReportStatus;
  findings: string;
  impression: string;
  finalized_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export type AuditAction = 'login' | 'view' | 'create' | 'update' | 'finalize' | 'download';
export type AuditEntity = 'session' | 'patient' | 'study' | 'report';

export interface AuditEvent {
  id: string;
  actor_id: string | null;
  actor_email: string;
  actor_role: UserRole;
  action: AuditAction;
  entity_type: AuditEntity;
  entity_id: string | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export type EncounterStatus = 'planned' | 'in-progress' | 'finished' | 'cancelled';

export interface Encounter {
  id: string;
  patient_id: string;
  referring_clinician_id: string | null;
  status: EncounterStatus;
  reason: string | null;
  occurred_at: string | null;
  notes: string | null;
  extra: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}
