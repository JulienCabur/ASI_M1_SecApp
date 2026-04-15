export type Role = 'role_patients' | 'role_docteurs';

export interface User {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  role: Role;
}

export interface Doctor {
  id: string;
  firstName: string;
  lastName: string;
  specialty: string;
  userId: string;
}

export interface MedicalFile {
  id: string;
  name: string;
  date: string;
  type: string;
  uploaderName: string;
  uploaderId: string;
  patientId: string;
  url?: string;
  requiresApproval: boolean;
}

export type NotificationType = 'file_upload' | 'file_edit' | 'file_delete' | 'doctor_add';
export type NotificationStatus = 'pending' | 'approved' | 'rejected';

export interface Notification {
  id: string;
  type: NotificationType;
  description: string;
  timestamp: string;
  status: NotificationStatus;
  targetPatientId: string;
  initiatorName: string;
  payload: Record<string, unknown>;
}
