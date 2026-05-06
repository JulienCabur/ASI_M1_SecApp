/**
 * Service notifications — synthétise des notifications à partir des relations
 * non vérifiées côté backend.
 *
 * Il n'y a pas de table notifications dédiée : la "demande d'ajout patient/
 * médecin" est représentée par une relation `is_verified=False`. On les
 * formate ici en `Notification` pour réutiliser l'UI existante.
 *
 *  - Côté patient : la relation entrante = un médecin demande accès au
 *    dossier ; le patient peut Approuver (wrap KEK pour chaque device du
 *    médecin) ou Refuser.
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
import { useCryptoStore } from '@/store/crypto.store';
import type { Notification, NotificationStatus } from '@/types';

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
        devices: r.devices.map((d) => ({ deviceId: d.device_id, publicKey: d.public_key })),
      },
    };
  });
};

/**
 * Résout une notification.
 *  - "approved" (incoming uniquement) : pour chaque device du médecin, on
 *    wrap la KEK locale avec sa clé publique et on appelle `patient_verify_doctor`.
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
    const devices = notification.payload.devices;
    if (devices.length === 0) {
      throw new Error('Aucun device médecin à vérifier pour cette demande.');
    }
    const kek = useCryptoStore.getState().kek;
    if (!kek) {
      throw new Error('Session cryptographique non initialisée. Reconnectez-vous.');
    }
    for (const dev of devices) {
      const recipientKey = await importPublicKeyJwk(dev.publicKey);
      const cipheredKek = await wrapKEKWithRecipientPublicKey(kek, recipientKey);
      await patientVerifyDoctor(dev.deviceId, cipheredKek);
    }
    return;
  }

  if (decision !== 'rejected') return;
  if (notification.direction === 'incoming') {
    await patientRemoveDoctor(notification.payload.counterpartId);
  } else {
    await doctorRemovePatient(notification.payload.counterpartId);
  }
};
