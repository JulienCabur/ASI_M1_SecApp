import { api } from '@/services/api';

/**
 * Référentiel hôpitaux exposé par le BFF (`GET /hospitals/list`).
 *
 * Sert à peupler la liste déroulante de l'enregistrement médecin. Le back
 * revalide systématiquement le champ `organization` contre ce référentiel
 * côté serveur (cf. `AuthService._assert_known_hospital`) — on ne fait donc
 * jamais confiance à la sélection front pour la décision finale.
 */
interface HospitalsResponse {
  hospitals: string[];
}

export const listHospitals = async (): Promise<string[]> => {
  const { data } = await api.get<HospitalsResponse>('/hospitals/list');
  return data.hospitals ?? [];
};
