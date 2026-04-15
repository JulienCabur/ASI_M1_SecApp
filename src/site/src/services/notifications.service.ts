import type { Notification, NotificationStatus } from '@/types';

let mockNotifications: Notification[] = [
  {
    id: 'n1',
    type: 'file_upload',
    description: 'Dr. Jean Bernard souhaite téléverser "Résultats IRM" dans votre dossier.',
    timestamp: '2025-04-07T10:30:00Z',
    status: 'pending',
    targetPatientId: 'mock-patient',
    initiatorName: 'Dr. Jean Bernard',
    payload: { fileName: 'Résultats IRM', fileType: 'application/pdf' },
  },
  {
    id: 'n2',
    type: 'doctor_add',
    description: 'Dr. Claire Martin demande à accéder à votre dossier médical.',
    timestamp: '2025-04-06T14:00:00Z',
    status: 'pending',
    targetPatientId: 'mock-patient',
    initiatorName: 'Dr. Claire Martin',
    payload: { doctorId: 'd3' },
  },
  {
    id: 'n3',
    type: 'file_edit',
    description: 'Dr. Marie Dupont souhaite modifier "Bilan sanguin 2024.pdf".',
    timestamp: '2025-04-05T09:15:00Z',
    status: 'approved',
    targetPatientId: 'mock-patient',
    initiatorName: 'Dr. Marie Dupont',
    payload: { fileId: 'f1' },
  },
  {
    id: 'n4',
    type: 'file_delete',
    description: 'Dr. Jean Bernard souhaite supprimer "Radio thorax.png".',
    timestamp: '2025-04-04T16:45:00Z',
    status: 'rejected',
    targetPatientId: 'mock-patient',
    initiatorName: 'Dr. Jean Bernard',
    payload: { fileId: 'f2' },
  },
];

const delay = (ms = 100) => new Promise<void>((r) => setTimeout(r, ms));

export const getNotifications = async (_userId: string): Promise<Notification[]> => {
  await delay();
  return [...mockNotifications];
};

export const resolveNotification = async (
  id: string,
  decision: NotificationStatus
): Promise<void> => {
  await delay();
  mockNotifications = mockNotifications.map((n) =>
    n.id === id ? { ...n, status: decision } : n
  );
};

export const addNotification = async (notification: Omit<Notification, 'id'>): Promise<Notification> => {
  await delay();
  const newNotif: Notification = {
    ...notification,
    id: `n${Date.now()}`,
  };
  mockNotifications.push(newNotif);
  return newNotif;
};
