import type { MedicalFile, Role } from '@/types';

let mockFiles: MedicalFile[] = [
  {
    id: 'f1',
    name: 'Bilan sanguin 2024.pdf',
    date: '2024-03-15',
    type: 'application/pdf',
    uploaderName: 'Dr. Marie Dupont',
    uploaderId: 'u-doc-1',
    patientId: 'mock-patient',
    url: undefined,
    requiresApproval: false,
  },
  {
    id: 'f2',
    name: 'Radio thorax.png',
    date: '2024-06-01',
    type: 'image/png',
    uploaderName: 'Dr. Jean Bernard',
    uploaderId: 'u-doc-2',
    patientId: 'mock-patient',
    url: undefined,
    requiresApproval: false,
  },
  {
    id: 'f3',
    name: 'Ordonnance antibiotiques.pdf',
    date: '2025-01-10',
    type: 'application/pdf',
    uploaderName: 'Patient',
    uploaderId: 'mock-patient',
    patientId: 'mock-patient',
    url: undefined,
    requiresApproval: false,
  },
];

let nextId = 10;

const delay = (ms = 100) => new Promise<void>((r) => setTimeout(r, ms));

export const getFiles = async (patientId: string): Promise<MedicalFile[]> => {
  await delay();
  return mockFiles.filter((f) => f.patientId === patientId);
};

export const uploadFile = async (
  patientId: string,
  file: File,
  uploaderName: string,
  uploaderId: string,
  uploaderRole: Role
): Promise<MedicalFile> => {
  await delay();
  const newFile: MedicalFile = {
    id: `f${nextId++}`,
    name: file.name,
    date: new Date().toISOString().slice(0, 10),
    type: file.type || 'application/octet-stream',
    uploaderName,
    uploaderId,
    patientId,
    url: URL.createObjectURL(file),
    requiresApproval: uploaderRole === 'role_docteurs',
  };
  mockFiles.push(newFile);
  return newFile;
};

export const deleteFile = async (fileId: string): Promise<void> => {
  await delay();
  mockFiles = mockFiles.filter((f) => f.id !== fileId);
};

export const replaceFile = async (
  fileId: string,
  newFile: File,
  uploaderName: string,
  uploaderId: string,
  uploaderRole: Role
): Promise<MedicalFile> => {
  await delay();
  const existing = mockFiles.find((f) => f.id === fileId);
  if (!existing) throw new Error('File not found');

  const replaced: MedicalFile = {
    ...existing,
    name: newFile.name,
    date: new Date().toISOString().slice(0, 10),
    type: newFile.type || 'application/octet-stream',
    uploaderName,
    uploaderId,
    url: URL.createObjectURL(newFile),
    requiresApproval: uploaderRole === 'role_docteurs',
  };
  mockFiles = mockFiles.map((f) => (f.id === fileId ? replaced : f));
  return replaced;
};
