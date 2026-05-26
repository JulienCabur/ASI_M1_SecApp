import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, List, Modal, Space, Spin, Table, Tag, Typography, Upload } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';
import { useAuth } from '@/hooks/useAuth';
import {
  deleteFile,
  deleteFileForDoctor,
  downloadFile,
  getDoctorPendingRequests,
  getPendingRequests,
  listFiles,
  rejectRequest,
  uploadFile,
  uploadFileForDoctor,
  validateRequest,
  type DecryptedFile,
  type FileContext,
  type RemoteFile,
} from '@/services/files.service';
import { getPatientKek } from '@/services/relation.service';
import {
  loadPrivateKey,
  unwrapKEKWithRSAKey,
  unwrapPatientKEKWithPrivateMEK,
} from '@/services/crypto.service';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import { useNotificationsStore } from '@/store/notifications.store';
import type { PendingFileRequest } from '@/types';
import style from './dossier.module.scss';

const { Title } = Typography;
const { Dragger } = Upload;

interface PreviewState {
  filename: string;
  url: string;
  mime: string;
}

const operationLabel: Record<PendingFileRequest['operationType'], string> = {
  create: 'Ajout',
  update: 'Modification',
  delete: 'Suppression',
};

const operationColor: Record<PendingFileRequest['operationType'], string> = {
  create: 'green',
  update: 'blue',
  delete: 'red',
};

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const Dossier: React.FC = () => {
  const { user } = useAuth();
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const ownKek = useCryptoStore((s) => s.kek);
  const { setFileRequests } = useNotificationsStore();

  // Mode "médecin visualise dossier patient" via query string ?patient=<id>&name=<username>.
  const patientId = searchParams.get('patient');
  const patientName = searchParams.get('name') ?? patientId ?? '';
  const isViewingPatient = Boolean(patientId);

  // En mode patient-view, on déballe une KEK dédiée à la session de visu :
  // jamais persistée, jetée au démontage de la page.
  const [patientKek, setPatientKek] = useState<CryptoKey | null>(null);
  const [unwrapping, setUnwrapping] = useState(false);

  const [files, setFiles] = useState<RemoteFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);

  // Demandes en attente
  const [pendingRequests, setPendingRequests] = useState<PendingFileRequest[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);

  const activeKek = isViewingPatient ? patientKek : ownKek;
  const cryptoReady = useMemo(() => Boolean(activeKek), [activeKek]);

  const ctx = useMemo<FileContext | undefined>(() => {
    if (!isViewingPatient) return undefined;
    return patientKek ? { kek: patientKek, patientId: patientId ?? undefined } : undefined;
  }, [isViewingPatient, patientKek, patientId]);

  // Bootstrap : récupère le ciphered_kek patient et l'unwrap localement.
  // Pour un médecin : avec la privée MEK en mémoire de session.
  // Pour un patient (cas legacy) : avec la privée RSA du device.
  useEffect(() => {
    if (!isViewingPatient || !patientId) return;
    let cancelled = false;
    setUnwrapping(true);
    (async () => {
      try {
        const cipheredKekB64 = await getPatientKek(patientId);
        const wrapped = fromBase64(cipheredKekB64);
        const role = useAuthStore.getState().role;

        let kek: CryptoKey;
        if (role === 'role_docteurs') {
          // La KEK patient a été wrappée par le patient avec la public MEK
          // du médecin. Seule la privée MEK (en mémoire de session) déballe.
          const privateMEK = useCryptoStore.getState().privateMEK;
          if (!privateMEK) {
            throw new Error('Privée MEK absente — reconnectez-vous.');
          }
          kek = await unwrapPatientKEKWithPrivateMEK(wrapped, privateMEK);
        } else {
          // Cas legacy : non-médecin qui consulte un dossier patient (ne devrait
          // pas arriver via l'UI mais on garde le path par sécurité).
          const privateKey = await loadPrivateKey();
          if (!privateKey) throw new Error('Clé privée introuvable dans IndexedDB.');
          kek = await unwrapKEKWithRSAKey(wrapped, privateKey);
        }
        if (!cancelled) setPatientKek(kek);
      } catch (err) {
        if (!cancelled) {
          console.error('[Dossier] patient kek unwrap error:', err);
          void message.error(`Impossible de déballer la clé patient : ${(err as Error).message}`);
        }
      } finally {
        if (!cancelled) setUnwrapping(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isViewingPatient, patientId, message]);

  // Au démontage / changement de patient : purger la KEK patient de la mémoire.
  useEffect(() => {
    return () => setPatientKek(null);
  }, [patientId]);

  const loadFiles = useCallback(async () => {
    if (!activeKek) return;
    setLoading(true);
    try {
      setFiles(await listFiles(ctx));
    } catch (err) {
      message.error(`Impossible de charger les fichiers : ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [message, ctx, activeKek]);

  const loadPendingRequests = useCallback(async () => {
    if (!activeKek) return;
    setPendingLoading(true);
    try {
      if (isViewingPatient && patientId) {
        const list = await getDoctorPendingRequests(activeKek, patientId);
        setPendingRequests(list);
      } else {
        const list = await getPendingRequests(activeKek);
        setPendingRequests(list);
        setFileRequests(list);
      }
    } catch (err) {
      console.error('[Dossier] pending requests error:', err);
    } finally {
      setPendingLoading(false);
    }
  }, [activeKek, isViewingPatient, patientId, setFileRequests]);

  useEffect(() => {
    if (!user) return;
    void loadFiles();
    void loadPendingRequests();
  }, [user, loadFiles, loadPendingRequests]);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  const handleUpload = async () => {
    const raw = fileList[0]?.originFileObj;
    if (!raw) return;
    setUploading(true);
    try {
      if (isViewingPatient && ctx?.kek && ctx.patientId) {
        await uploadFileForDoctor(raw as File, { kek: ctx.kek, patientId: ctx.patientId });
        message.success(`Demande d'ajout de "${raw.name}" envoyée au patient pour validation.`);
        await loadPendingRequests();
      } else {
        await uploadFile(raw as File, ctx);
        message.success(`"${raw.name}" téléversé et chiffré.`);
        await loadFiles();
      }
      setUploadVisible(false);
      setFileList([]);
    } catch (err) {
      message.error(`Échec du téléversement : ${(err as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  const decryptAndOpen = async (file: RemoteFile, asDownload: boolean) => {
    try {
      const decrypted = await downloadFile(file, ctx);
      if (asDownload) {
        triggerBrowserDownload(decrypted);
      } else {
        const url = URL.createObjectURL(decrypted.blob);
        if (preview) URL.revokeObjectURL(preview.url);
        setPreview({ filename: decrypted.filename, url, mime: decrypted.blob.type });
      }
    } catch (err) {
      message.error(`Déchiffrement impossible : ${(err as Error).message}`);
    }
  };

  const handleDelete = (file: RemoteFile) => {
    if (isViewingPatient && patientId) {
      modal.confirm({
        title: 'Demander la suppression de ce fichier ?',
        content: `Une demande de suppression de "${file.name}" sera envoyée au patient pour validation.`,
        okText: 'Envoyer la demande',
        okType: 'danger',
        cancelText: 'Annuler',
        onOk: async () => {
          try {
            await deleteFileForDoctor(file.id, patientId);
            message.success('Demande de suppression envoyée au patient pour validation.');
            await loadPendingRequests();
          } catch (err) {
            message.error(`Échec de la demande : ${(err as Error).message}`);
          }
        },
      });
    } else {
      modal.confirm({
        title: 'Supprimer ce fichier ?',
        content: `"${file.name}" sera retiré du serveur. Action irréversible.`,
        okText: 'Supprimer',
        okType: 'danger',
        cancelText: 'Annuler',
        onOk: async () => {
          try {
            await deleteFile(file.id, ctx);
            message.success('Fichier supprimé.');
            await loadFiles();
          } catch (err) {
            message.error(`Suppression impossible : ${(err as Error).message}`);
          }
        },
      });
    }
  };

  const handleValidate = async (req: PendingFileRequest) => {
    setPendingActionId(req.fileRequestId);
    try {
      await validateRequest(req.fileRequestId);
      message.success('Demande approuvée.');
      await Promise.all([loadPendingRequests(), loadFiles()]);
    } catch (err) {
      message.error(`Approbation impossible : ${(err as Error).message}`);
    } finally {
      setPendingActionId(null);
    }
  };

  const handleReject = async (req: PendingFileRequest) => {
    setPendingActionId(req.fileRequestId);
    try {
      await rejectRequest(req.fileRequestId);
      message.success('Demande refusée.');
      await loadPendingRequests();
    } catch (err) {
      message.error(`Refus impossible : ${(err as Error).message}`);
    } finally {
      setPendingActionId(null);
    }
  };

  const closePreview = () => {
    if (preview) URL.revokeObjectURL(preview.url);
    setPreview(null);
  };

  const renderPreview = () => {
    if (!preview) return null;
    if (preview.mime.startsWith('image/')) {
      return <img src={preview.url} alt={preview.filename} style={{ maxWidth: '100%', maxHeight: '70vh' }} />;
    }
    if (preview.mime === 'application/pdf') {
      return <iframe src={preview.url} title={preview.filename} style={{ width: '100%', height: '70vh', border: 'none' }} />;
    }
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <p>Aperçu non disponible pour ce type de fichier.</p>
        <Button type="primary" href={preview.url} download={preview.filename}>
          Télécharger
        </Button>
      </div>
    );
  };

  const renderPendingSection = () => {
    if (pendingLoading) {
      return <Spin size="small" style={{ marginBottom: 16 }} />;
    }
    if (pendingRequests.length === 0) return null;

    const title = isViewingPatient
      ? `Mes propositions en attente (${pendingRequests.length})`
      : `Demandes en attente de votre médecin (${pendingRequests.length})`;

    return (
      <div style={{ marginBottom: 24 }}>
        <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
          {title}
        </Typography.Text>
        <List
          bordered
          size="small"
          dataSource={pendingRequests}
          renderItem={(req) => (
            <List.Item
              key={req.fileRequestId}
              actions={
                isViewingPatient
                  ? [<Tag key="status" color="processing">En attente</Tag>]
                  : [
                      <Button
                        key="approve"
                        type="primary"
                        size="small"
                        loading={pendingActionId === req.fileRequestId}
                        disabled={pendingActionId !== null && pendingActionId !== req.fileRequestId}
                        onClick={() => handleValidate(req)}
                      >
                        Approuver
                      </Button>,
                      <Button
                        key="reject"
                        danger
                        size="small"
                        disabled={pendingActionId !== null}
                        onClick={() => handleReject(req)}
                      >
                        Refuser
                      </Button>,
                    ]
              }
            >
              <Space>
                <Tag color={operationColor[req.operationType]}>{operationLabel[req.operationType]}</Tag>
                <Typography.Text>{req.fileName}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>{req.date}</Typography.Text>
              </Space>
            </List.Item>
          )}
        />
      </div>
    );
  };

  const columns: ColumnsType<RemoteFile> = [
    { title: 'Nom', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: 'Date', dataIndex: 'date', key: 'date', width: 200 },
    {
      title: 'Actions',
      key: 'actions',
      width: 300,
      render: (_, file) => (
        <Space>
          <Button size="small" disabled={!cryptoReady} onClick={() => decryptAndOpen(file, false)}>
            Voir
          </Button>
          <Button size="small" disabled={!cryptoReady} onClick={() => decryptAndOpen(file, true)}>
            Télécharger
          </Button>
          <Button size="small" danger onClick={() => handleDelete(file)}>
            {isViewingPatient ? 'Demander suppression' : 'Supprimer'}
          </Button>
        </Space>
      ),
    },
  ];

  const uploadProps = {
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList: list }: { fileList: UploadFile[] }) => setFileList(list.slice(-1)),
    maxCount: 1,
  };

  if (isViewingPatient && unwrapping) {
    return (
      <div className={style.container} style={{ textAlign: 'center', paddingTop: 64 }}>
        <Spin size="large" tip="Déballage de la clé patient..." />
      </div>
    );
  }

  return (
    <div className={style.container}>
      <div className={style.header}>
        <Space direction="vertical" size={4}>
          {isViewingPatient && (
            <Button size="small" onClick={() => navigate('/patients')} style={{ paddingLeft: 0 }} type="link">
              ← Retour aux patients
            </Button>
          )}
          <Title level={2} style={{ margin: 0 }}>
            {isViewingPatient ? `Dossier de ${patientName}` : 'Mon dossier médical'}
          </Title>
        </Space>
        <Button
          type="primary"
          disabled={!cryptoReady}
          onClick={() => { setUploadVisible(true); setFileList([]); }}
        >
          {isViewingPatient ? 'Proposer un fichier' : 'Téléverser un fichier'}
        </Button>
      </div>

      {isViewingPatient && (
        <Alert
          type="info"
          showIcon
          message="Mode médecin — modifications soumises à validation"
          description="Les fichiers que vous proposez et les suppressions que vous demandez seront soumis à la validation du patient avant d'être appliqués."
          style={{ marginBottom: 16 }}
        />
      )}

      {!cryptoReady && !unwrapping && (
        <Alert
          type="warning"
          showIcon
          message="Session crypto indisponible"
          description={
            isViewingPatient
              ? "La KEK patient n'a pas pu être déballée. Vérifiez que la relation est validée par ce device."
              : "La KEK n'a pas pu être restaurée pour cet appareil. Le chiffrement et le déchiffrement local sont désactivés."
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {renderPendingSection()}

      <Table
        columns={columns}
        dataSource={files}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: 'Aucun fichier dans le dossier' }}
      />

      <Modal
        title={preview?.filename}
        open={!!preview}
        onCancel={closePreview}
        footer={null}
        width={800}
      >
        {renderPreview()}
      </Modal>

      <Modal
        title={isViewingPatient ? 'Proposer un fichier au patient' : 'Téléverser un fichier'}
        open={uploadVisible}
        onCancel={() => setUploadVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setUploadVisible(false)}>Annuler</Button>,
          <Button
            key="upload"
            type="primary"
            loading={uploading}
            disabled={fileList.length === 0 || !cryptoReady}
            onClick={handleUpload}
          >
            {isViewingPatient ? 'Envoyer la proposition' : 'Téléverser'}
          </Button>,
        ]}
      >
        <Alert
          type="info"
          showIcon
          message={
            isViewingPatient
              ? "Le fichier sera chiffré avec la clé du patient et soumis à sa validation avant d'être ajouté à son dossier."
              : "Le fichier est chiffré localement avant envoi. Le serveur ne voit jamais son contenu en clair."
          }
          style={{ marginBottom: 16 }}
        />
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">Cliquez ou glissez un fichier ici</p>
          <p className="ant-upload-hint">Tout type de fichier accepté</p>
        </Dragger>
      </Modal>
    </div>
  );
};

const triggerBrowserDownload = ({ blob, filename }: DecryptedFile): void => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export default Dossier;
