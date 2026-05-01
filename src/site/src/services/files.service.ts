/**
 * Service fichiers — chiffrement de bout en bout.
 *
 * Modèle d'envelope :
 *  - DEK AES-GCM 256 fraîche par fichier (jamais réutilisée), tirée par
 *    crypto.service.ts.
 *  - Le DEK est wrappé par la KEK de session, donc seul le détenteur de la
 *    privée RSA (et donc de la KEK) peut décoder le fichier.
 *  - Le backend stocke un seul champ `ciphered_dek` par fichier ; on y met
 *    une enveloppe JSON-puis-base64 contenant `{ fileIv, wrappedDek, dekIv }`.
 *  - Le contenu chiffré (AES-GCM) est envoyé comme corps multipart classique.
 *
 * Le serveur n'a donc accès qu'à du ciphertext opaque + une enveloppe
 * inutilisable sans la KEK : confidentialité de bout en bout, indépendamment
 * du fait qu'un admin DB puisse lire les lignes.
 */

import { api } from '@/services/api';
import {
  decryptFileWithKEK,
  decryptMetadataWithKEK,
  encryptFileWithKEK,
  type EncryptedFile,
} from '@/services/crypto.service';
import { useCryptoStore } from '@/store/crypto.store';

export interface RemoteFile {
  id: string;
  name: string;
  date: string;
  cipheredDek: string;
}

interface ListFilesResponse {
  files: { name: string; date: string; ciphered_dek: string }[];
}

interface DownloadResponse {
  file_content: string; // base64 du ciphertext stocké côté serveur
  key: string;
  filename: string;
}

interface DekEnvelope {
  fileIv: string;
  wrappedDek: string;
  dekIv: string;
  nameIv: string;
  dateIv: string;
}

const toBase64 = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
};

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const toBase64Url = (buf: ArrayBuffer): string =>
  toBase64(buf).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

const fromBase64Url = (b64url: string): ArrayBuffer => {
  const padded = b64url.replace(/-/g, '+').replace(/_/g, '/');
  const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4));
  return fromBase64(padded + pad);
};

const encodeEnvelope = (
  enc: Pick<EncryptedFile, 'fileIv' | 'wrappedDek' | 'dekIv' | 'nameIv' | 'dateIv'>,
): string =>
  btoa(
    JSON.stringify({
      fileIv: toBase64(enc.fileIv),
      wrappedDek: toBase64(enc.wrappedDek),
      dekIv: toBase64(enc.dekIv),
      nameIv: toBase64(enc.nameIv),
      dateIv: toBase64(enc.dateIv),
    } satisfies DekEnvelope),
  );

const decodeEnvelope = (
  encoded: string,
): Pick<EncryptedFile, 'fileIv' | 'wrappedDek' | 'dekIv' | 'nameIv' | 'dateIv'> => {
  const json = JSON.parse(atob(encoded)) as DekEnvelope;
  return {
    fileIv: fromBase64(json.fileIv),
    wrappedDek: fromBase64(json.wrappedDek),
    dekIv: fromBase64(json.dekIv),
    nameIv: fromBase64(json.nameIv),
    dateIv: fromBase64(json.dateIv),
  };
};

const requireKek = (): CryptoKey => {
  const kek = useCryptoStore.getState().kek;
  if (!kek) {
    throw new Error('Session crypto non initialisée — clé KEK absente.');
  }
  return kek;
};

export const listFiles = async (): Promise<RemoteFile[]> => {
  const kek = requireKek();
  const { data } = await api.get<ListFilesResponse>('/files/list_files');
  const decrypted = await Promise.all(
    data.files.map(async (f) => {
      const env = decodeEnvelope(f.ciphered_dek);
      const meta = await decryptMetadataWithKEK(
        {
          ...env,
          nameCiphertext: fromBase64Url(f.name),
          dateCiphertext: fromBase64(f.date),
        },
        kek,
      );
      return {
        id: f.name,
        name: meta.name,
        date: meta.date,
        cipheredDek: f.ciphered_dek,
      };
    }),
  );
  return decrypted;
};

export const uploadFile = async (file: File): Promise<void> => {
  const kek = requireKek();
  const plain = await file.arrayBuffer();
  const enc = await encryptFileWithKEK(
    plain,
    { name: file.name, date: new Date().toISOString() },
    kek,
  );
  const envelope = encodeEnvelope(enc);
  const cipheredName = toBase64Url(enc.nameCiphertext);
  const cipheredDate = toBase64(enc.dateCiphertext);

  const form = new FormData();
  form.append('file', new Blob([enc.ciphertext]), cipheredName);
  await api.post('/files/upload_file', form, {
    params: { dek: envelope, date: cipheredDate },
  });
};

export interface DecryptedFile {
  blob: Blob;
  filename: string;
}

const guessMimeType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  switch (ext) {
    case 'pdf': return 'application/pdf';
    case 'png': return 'image/png';
    case 'jpg':
    case 'jpeg': return 'image/jpeg';
    case 'gif': return 'image/gif';
    case 'webp': return 'image/webp';
    case 'svg': return 'image/svg+xml';
    case 'txt': return 'text/plain';
    case 'json': return 'application/json';
    default: return 'application/octet-stream';
  }
};

export const downloadFile = async (file: RemoteFile): Promise<DecryptedFile> => {
  const kek = requireKek();
  const { data } = await api.get<DownloadResponse>('/files/download_file', {
    params: { file: file.id },
  });
  const env = decodeEnvelope(data.key);
  const plain = await decryptFileWithKEK(
    {
      ciphertext: fromBase64(data.file_content),
      fileIv: env.fileIv,
      wrappedDek: env.wrappedDek,
      dekIv: env.dekIv,
    },
    kek,
  );
  return {
    blob: new Blob([plain], { type: guessMimeType(file.name) }),
    filename: file.name,
  };
};

export const deleteFile = async (id: string): Promise<void> => {
  await api.post('/files/delete_file', null, { params: { file: id } });
};
