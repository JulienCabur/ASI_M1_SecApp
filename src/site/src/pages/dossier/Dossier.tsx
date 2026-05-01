import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Modal, Space, Table, Typography, Upload } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';
import { useAuth } from '@/hooks/useAuth';
import { deleteFile, downloadFile, listFiles, uploadFile, type DecryptedFile, type RemoteFile } from '@/services/files.service';
import { useCryptoStore } from '@/store/crypto.store';
import style from './dossier.module.scss';

const { Title } = Typography;
const { Dragger } = Upload;

interface PreviewState {
  filename: string;
  url: string;
  mime: string;
}

const Dossier: React.FC = () => {
  const { user } = useAuth();
  const { message, modal } = App.useApp();
  const kek = useCryptoStore((s) => s.kek);

  const [files, setFiles] = useState<RemoteFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);

  const cryptoReady = useMemo(() => Boolean(kek), [kek]);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      setFiles(await listFiles());
    } catch (err) {
      message.error(`Impossible de charger les fichiers : ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    if (!user) return;
    loadFiles();
  }, [user, loadFiles]);

  // Libération des Object URLs pour éviter de garder le buffer déchiffré
  // accroché à un Blob URL au-delà de l'usage.
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
      await uploadFile(raw as File);
      message.success(`"${raw.name}" téléversé et chiffré.`);
      setUploadVisible(false);
      setFileList([]);
      await loadFiles();
    } catch (err) {
      message.error(`Échec du téléversement : ${(err as Error).message}`);
    } finally {
      setUploading(false);
    }
  };

  const decryptAndOpen = async (file: RemoteFile, asDownload: boolean) => {
    try {
      const decrypted = await downloadFile(file.name);
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
    modal.confirm({
      title: 'Supprimer ce fichier ?',
      content: `"${file.name}" sera retiré du serveur. Action irréversible.`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await deleteFile(file.name);
          message.success('Fichier supprimé.');
          await loadFiles();
        } catch (err) {
          message.error(`Suppression impossible : ${(err as Error).message}`);
        }
      },
    });
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

  const columns: ColumnsType<RemoteFile> = [
    { title: 'Nom', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: 'Date', dataIndex: 'date', key: 'date', width: 200 },
    {
      title: 'Actions',
      key: 'actions',
      width: 280,
      render: (_, file) => (
        <Space>
          <Button size="small" disabled={!cryptoReady} onClick={() => decryptAndOpen(file, false)}>
            Voir
          </Button>
          <Button size="small" disabled={!cryptoReady} onClick={() => decryptAndOpen(file, true)}>
            Télécharger
          </Button>
          <Button size="small" danger onClick={() => handleDelete(file)}>
            Supprimer
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

  return (
    <div className={style.container}>
      <div className={style.header}>
        <Title level={2} style={{ margin: 0 }}>Mon dossier médical</Title>
        <Button
          type="primary"
          disabled={!cryptoReady}
          onClick={() => { setUploadVisible(true); setFileList([]); }}
        >
          Téléverser un fichier
        </Button>
      </div>

      {!cryptoReady && (
        <Alert
          type="warning"
          showIcon
          message="Session crypto indisponible"
          description="La KEK n'a pas pu être restaurée pour cet appareil. Le chiffrement et le déchiffrement local sont désactivés. Reconnecte-toi ou réinitialise l'appareil depuis Crypto Lab."
          style={{ marginBottom: 16 }}
        />
      )}

      <Table
        columns={columns}
        dataSource={files}
        rowKey="name"
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
        title="Téléverser un fichier"
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
            Téléverser
          </Button>,
        ]}
      >
        <Alert
          type="info"
          showIcon
          message="Le fichier est chiffré localement avant envoi. Le serveur ne voit jamais son contenu en clair."
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
