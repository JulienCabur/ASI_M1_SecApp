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

export type FileOperationType = 'create' | 'update' | 'delete';

export interface PendingFileRequest {
  fileRequestId: string;
  relationId: string;
  doctorId: string;
  operationType: FileOperationType;
  fileName: string;
  date: string;
  encryptedFileName: string;
}

export type NotificationType = 'doctor_add' | 'patient_add';
export type NotificationStatus = 'pending' | 'approved' | 'rejected';
export type NotificationDirection = 'incoming' | 'outgoing';

export interface Notification {
  id: string;
  type: NotificationType;
  direction: NotificationDirection;
  description: string;
  status: NotificationStatus;
  initiatorName: string;
  payload: {
    counterpartId: string;
    /** JWK publique MEK du médecin demandeur (uniquement pour les notifs
     *  "incoming" côté patient). null pour les notifs sortantes. */
    publicMek: JsonWebKey | null;
  };
}
