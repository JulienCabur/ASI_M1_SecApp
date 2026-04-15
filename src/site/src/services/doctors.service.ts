import type { Doctor } from '@/types';

const MOCK_DOCTORS: Doctor[] = [
  { id: 'd1', firstName: 'Marie', lastName: 'Dupont', specialty: 'Médecine générale', userId: 'u-doc-1' },
  { id: 'd2', firstName: 'Jean', lastName: 'Bernard', specialty: 'Cardiologie', userId: 'u-doc-2' },
  { id: 'd3', firstName: 'Claire', lastName: 'Martin', specialty: 'Neurologie', userId: 'u-doc-3' },
  { id: 'd4', firstName: 'Pierre', lastName: 'Leroy', specialty: 'Dermatologie', userId: 'u-doc-4' },
  { id: 'd5', firstName: 'Sophie', lastName: 'Moreau', specialty: 'Pédiatrie', userId: 'u-doc-5' },
];

// Simulates per-patient doctor lists
const patientDoctors: Record<string, string[]> = {
  'mock-patient': ['d1', 'd2'],
};

const delay = (ms = 100) => new Promise<void>((r) => setTimeout(r, ms));

export const getDoctors = async (patientId: string): Promise<Doctor[]> => {
  await delay();
  const ids = patientDoctors[patientId] ?? [];
  return MOCK_DOCTORS.filter((d) => ids.includes(d.id));
};

export const searchDoctors = async (query: string): Promise<Doctor[]> => {
  await delay();
  const q = query.toLowerCase();
  return MOCK_DOCTORS.filter(
    (d) =>
      d.firstName.toLowerCase().includes(q) ||
      d.lastName.toLowerCase().includes(q) ||
      d.specialty.toLowerCase().includes(q)
  );
};

export const addDoctor = async (patientId: string, doctorId: string): Promise<void> => {
  await delay();
  if (!patientDoctors[patientId]) patientDoctors[patientId] = [];
  if (!patientDoctors[patientId].includes(doctorId)) {
    patientDoctors[patientId].push(doctorId);
  }
};

export const removeDoctor = async (patientId: string, doctorId: string): Promise<void> => {
  await delay();
  if (patientDoctors[patientId]) {
    patientDoctors[patientId] = patientDoctors[patientId].filter((id) => id !== doctorId);
  }
};
