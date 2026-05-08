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

/** Format renvoyé par `get_unverified_relations` :
 *  - direction="incoming" : l'user courant est le patient à approuver. La
 *    `public_mek` est la JWK publique MEK du médecin demandeur, utilisée par
 *    le patient pour wrap sa KEK une seule fois (au niveau user médecin).
 *  - direction="outgoing" : l'user courant est le médecin en attente —
 *    `public_mek` n'est pas pertinent ici (null). */
export interface UnverifiedRelation {
  counterpart_id: string;
  username: string;
  role: string | null;
  direction: 'incoming' | 'outgoing';
  public_mek: JsonWebKey | null;
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

/** Une relation fraîchement créée par `patient_add_doctor` : un objet par device
 *  du médecin, avec la public_key RSA-OAEP nécessaire pour wrap la KEK. */
export interface CreatedRelation {
  relation_id: string;
  public_key: JsonWebKey;
}

interface PatientAddDoctorResponse {
  relations: { relation: CreatedRelation[] };
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
export const patientAddDoctor = async (doctorId: string): Promise<CreatedRelation[]> => {
  const form = new URLSearchParams();
  form.append('doctor_id', doctorId);
  const { data } = await api.post<PatientAddDoctorResponse>('/relation/patient_add_doctor', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data.relations?.relation ?? [];
};

/** Stocke la KEK patient (wrappée avec la public_key d'un device médecin) sur
 *  une relation précise. À appeler juste après `patientAddDoctor` pour chaque
 *  device retourné, sinon le médecin ne pourra pas déchiffrer le dossier. */
export const storeRelationKek = async (
  relationId: string,
  cipheredKek: string,
): Promise<void> => {
  const form = new URLSearchParams();
  form.append('relation_id', relationId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/relation/store_kek', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
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

/** Patient → vérifie la relation avec un médecin (au niveau user, plus par
 *  device). La KEK doit avoir été wrappée localement avec la public MEK du
 *  médecin remontée par `get_unverified_relations`. */
export const patientVerifyDoctor = async (
  doctorId: string,
  cipheredKek: string,
): Promise<void> => {
  const form = new URLSearchParams();
  form.append('doctor_id', doctorId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/relation/patient_verify_doctor', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

/** Médecin → récupère la KEK patient (chiffrée par le patient avec la public
 *  MEK du médecin). À déballer localement avec la privée MEK en mémoire de
 *  session (cf. `unwrapPatientKEKWithPrivateMEK`). */
export const getPatientKek = async (patientId: string): Promise<string> => {
  const { data } = await api.get<{ ciphered_kek: string }>('/relation/get_patient_kek', {
    params: { patient_id: patientId },
  });
  return data.ciphered_kek;
};
