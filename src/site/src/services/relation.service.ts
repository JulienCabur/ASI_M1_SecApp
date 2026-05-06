/**
 * Service relation — gestion des liens patient/médecin via le BFF FastAPI.
 *
 * Le backend (`presentation/relation.py`) expose des endpoints qui attendent
 * du `application/x-www-form-urlencoded` (FastAPI `Form(...)`), donc on
 * envoie via `URLSearchParams` plutôt qu'en JSON, comme `device.service.ts`.
 */

import { api } from '@/services/api';

export interface RelationUser {
  id: string;
  username: string;
  roles: string;
}

export interface Relation {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_device_id: string | null;
  is_verified: boolean;
}

/** Format dédoublonné renvoyé par `get_relations` côté back :
 *  une entrée par contrepartie (patient ou médecin) avec son username. */
export interface RelationSummary {
  counterpart_id: string;
  username: string;
  role: string | null;
  is_verified: boolean;
}

/** Device d'un médecin : clé publique RSA-OAEP exportée en JWK, utilisée
 *  côté patient pour wrap sa KEK avant `patient_verify_doctor`. */
export interface RelationDevice {
  device_id: string;
  public_key: JsonWebKey;
}

/** Format renvoyé par `get_unverified_relations` :
 *  - direction="incoming" : l'user courant est le patient à approuver.
 *  - direction="outgoing" : l'user courant est le médecin en attente. */
export interface UnverifiedRelation {
  counterpart_id: string;
  username: string;
  role: string | null;
  direction: 'incoming' | 'outgoing';
  devices: RelationDevice[];
}

interface ListDoctorsResponse {
  doctors: RelationUser[];
}

interface RelationsResponse {
  relations: RelationSummary[];
}

interface UnverifiedRelationsResponse {
  unverified_relations: UnverifiedRelation[];
}

interface FindPatientResponse {
  patient: { id: string; username: string };
}

/** Liste tous les médecins disponibles (catalogue côté patient pour ajout). */
export const listDoctors = async (): Promise<RelationUser[]> => {
  const { data } = await api.get<ListDoctorsResponse>('/relation/list_doctors');
  return data.doctors ?? [];
};

/** Liste les relations de l'utilisateur courant (patient ou médecin),
 *  dédoublonnées par contrepartie et enrichies avec le username. */
export const getRelations = async (): Promise<RelationSummary[]> => {
  const { data } = await api.get<RelationsResponse>('/relation/get_relations');
  return data.relations ?? [];
};

/** Recherche un patient par username exact (côté médecin uniquement). */
export const findPatientByUsername = async (
  username: string,
): Promise<{ id: string; username: string }> => {
  const { data } = await api.get<FindPatientResponse>('/relation/find_patient', {
    params: { username },
  });
  return data.patient;
};

/** Liste les relations non vérifiées de l'utilisateur courant,
 *  dédoublonnées par contrepartie avec username et direction. */
export const getUnverifiedRelations = async (): Promise<UnverifiedRelation[]> => {
  const { data } = await api.get<UnverifiedRelationsResponse>('/relation/get_unverified_relations');
  return data.unverified_relations ?? [];
};

/** Patient → ajoute un médecin. Le back renvoie une liste de relations + clé
 *  publique de chaque device du médecin pour permettre le wrap de la KEK. */
export const patientAddDoctor = async (doctorId: string): Promise<unknown> => {
  const form = new URLSearchParams();
  form.append('doctor_id', doctorId);
  const { data } = await api.post('/relation/patient_add_doctor', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

/** Patient → supprime un médecin de ses relations. */
export const patientRemoveDoctor = async (doctorId: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('doctor_id', doctorId);
  await api.post('/relation/patient_remove_doctor', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

/** Médecin → ajoute un patient (par ID). Crée des relations non vérifiées
 *  qui devront être confirmées par le patient via `patient_verify_doctor`. */
export const doctorAddPatient = async (patientId: string): Promise<unknown> => {
  const form = new URLSearchParams();
  form.append('patient_id', patientId);
  const { data } = await api.post('/relation/doctor_add_patient', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

/** Médecin → supprime un patient de ses relations. */
export const doctorRemovePatient = async (patientId: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('patient_id', patientId);
  await api.post('/relation/doctor_remove_patient', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

/** Patient → vérifie une relation pour un device médecin précis. La KEK
 *  doit avoir été wrappée localement avec la public_key du device. */
export const patientVerifyDoctor = async (
  doctorDeviceId: string,
  cipheredKek: string,
): Promise<void> => {
  const form = new URLSearchParams();
  form.append('doctor_device_id', doctorDeviceId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/relation/patient_verify_doctor', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

/** Médecin → récupère la KEK patient (chiffrée) pour son device courant.
 *  À déballer localement avec la privée RSA d'IndexedDB pour pouvoir
 *  déchiffrer les fichiers du patient. */
export const getPatientKek = async (
  patientId: string,
  deviceId: string,
): Promise<string> => {
  const { data } = await api.get<{ ciphered_kek: string }>('/relation/get_patient_kek', {
    params: { patient_id: patientId, device_id: deviceId },
  });
  return data.ciphered_kek;
};
