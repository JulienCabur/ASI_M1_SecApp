/**
 * Service notifications — synthétise des notifications à partir des relations
 * non vérifiées côté backend.
 *
 * Il n'y a pas de table notifications dédiée : la "demande d'ajout patient/
 * médecin" est représentée par une relation `is_verified=False`. On les
 * formate ici en `Notification` pour réutiliser l'UI existante.
 *
 *  - Côté patient : la relation entrante = un médecin demande accès au
 *    dossier ; le patient peut Approuver (wrap sa KEK avec la public MEK du
 *    médecin, une seule fois au niveau user) ou Refuser.
 *  - Côté médecin : la relation sortante = il attend la confirmation du
 *    patient ; il peut Annuler la demande.
 */

import {
  doctorRemovePatient,
  getUnverifiedRelations,
  patientRemoveDoctor,
  patientVerifyDoctor,
} from '@/services/relation.service';
import {
  importPublicKeyJwk,
  wrapKEKWithRecipientPublicKey,
} from '@/services/crypto.service';
import { getPendingRequests } from '@/services/files.service';
import { useCryptoStore } from '@/store/crypto.store';
import type { Notification, NotificationStatus, PendingFileRequest } from '@/types';

export const getNotifications = async (): Promise<Notification[]> => {
  const unverified = await getUnverifiedRelations();
  return unverified.map((r): Notification => {
    const isIncoming = r.direction === 'incoming';
    return {
      id: r.counterpart_id,
      type: isIncoming ? 'doctor_add' : 'patient_add',
      direction: r.direction,
      status: 'pending',
      description: isIncoming
        ? `Le médecin ${r.username} demande à accéder à votre dossier.`
        : `Demande d'ajout du patient ${r.username} en attente de confirmation.`,
      initiatorName: r.username,
      payload: {
        counterpartId: r.counterpart_id,
        publicMek: r.public_mek,
      },
    };
  });
};

/** Récupère les demandes de fichiers en quarantaine pour le patient courant. */
export const getFilePendingRequests = async (): Promise<PendingFileRequest[]> => {
  const kek = useCryptoStore.getState().kek;
  if (!kek) return [];
  return getPendingRequests(kek);
};

/**
 * Résout une notification.
 *  - "approved" (incoming uniquement) : on wrap la KEK locale avec la public
 *    MEK du médecin et on appelle `patient_verify_doctor` une seule fois.
 *  - "rejected" : supprime la relation côté back (doctor ou patient selon
 *    la direction de la notif).
 */
export const resolveNotification = async (
  notification: Notification,
  decision: NotificationStatus,
): Promise<void> => {
  if (decision === 'approved') {
    if (notification.direction !== 'incoming') {
      throw new Error('Seul le destinataire (patient) peut approuver une demande.');
    }
    const publicMek = notification.payload.publicMek;
    if (!publicMek) {
      throw new Error('Public MEK du médecin absente — impossible d\'approuver.');
    }
    const kek = useCryptoStore.getState().kek;
    if (!kek) {
      throw new Error('Session cryptographique non initialisée. Reconnectez-vous.');
    }
    const recipientKey = await importPublicKeyJwk(publicMek);
    const cipheredKek = await wrapKEKWithRecipientPublicKey(kek, recipientKey);
    await patientVerifyDoctor(notification.payload.counterpartId, cipheredKek);
    return;
  }

  if (decision !== 'rejected') return;
  if (notification.direction === 'incoming') {
    await patientRemoveDoctor(notification.payload.counterpartId);
  } else {
    await doctorRemovePatient(notification.payload.counterpartId);
  }
};
