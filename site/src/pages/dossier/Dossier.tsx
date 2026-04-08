import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Modal,
  Space,
  Table,
  Typography,
  Upload,
  App,
} from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';
import { useAuth } from '@/hooks/useAuth';
import { getFiles, uploadFile, deleteFile, replaceFile } from '@/services/files.service';
import { addNotification, getNotifications } from '@/services/notifications.service';
import { useNotificationsStore } from '@/store/notifications.store';
import type { MedicalFile } from '@/types';
import style from './dossier.module.scss';

const { Title } = Typography;
const { Dragger } = Upload;

const Dossier: React.FC = () => {
  const { user } = useAuth();
  const { modal } = App.useApp();
  const { notifications, setNotifications } = useNotificationsStore();
  const isDoctor = user?.role === 'role_docteurs';
  const patientId = isDoctor ? 'mock-patient' : (user?.id ?? 'mock-patient');

  const [files, setFiles] = useState<MedicalFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewingFile, setViewingFile] = useState<MedicalFile | null>(null);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<MedicalFile | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  const loadFiles = () => {
    setLoading(true);
    getFiles(patientId)
      .then(setFiles)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadFiles();
  }, [patientId]);

  const handleUpload = async () => {
    const rawFile = fileList[0]?.originFileObj;
    if (!rawFile || !user) return;

    setUploading(true);
    try {
      if (isDoctor) {
        // Doctor upload requires patient approval — create a notification
        await addNotification({
          type: 'file_upload',
          description: `Dr. ${user.lastName} souhaite téléverser "${rawFile.name}" dans votre dossier.`,
          timestamp: new Date().toISOString(),
          status: 'pending',
          targetPatientId: patientId,
          initiatorName: `Dr. ${user.firstName} ${user.lastName}`,
          payload: { fileName: rawFile.name, fileType: rawFile.type },
        });
      } else {
        await uploadFile(patientId, rawFile, `${user.firstName} ${user.lastName}`, user.id, user.role);
        loadFiles();
      }
      setUploadVisible(false);
      setFileList([]);
    } finally {
      setUploading(false);
    }
  };

  const handleReplace = async () => {
    const rawFile = fileList[0]?.originFileObj;
    if (!rawFile || !replaceTarget || !user) return;

    setUploading(true);
    try {
      if (isDoctor) {
        await addNotification({
          type: 'file_edit',
          description: `Dr. ${user.lastName} souhaite modifier "${replaceTarget.name}".`,
          timestamp: new Date().toISOString(),
          status: 'pending',
          targetPatientId: patientId,
          initiatorName: `Dr. ${user.firstName} ${user.lastName}`,
          payload: { fileId: replaceTarget.id },
        });
        const updated = await getNotifications(user.id);
        setNotifications(updated);
      } else {
        await replaceFile(replaceTarget.id, rawFile, `${user.firstName} ${user.lastName}`, user.id, user.role);
        loadFiles();
      }
      setReplaceTarget(null);
      setFileList([]);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (file: MedicalFile) => {
    if (!user) return;

    if (isDoctor) {
      modal.confirm({
        title: 'Demande de suppression',
        content: `Une demande d'approbation sera envoyée au patient pour supprimer "${file.name}".`,
        okText: 'Envoyer la demande',
        cancelText: 'Annuler',
        onOk: async () => {
          await addNotification({
            type: 'file_delete',
            description: `Dr. ${user.lastName} souhaite supprimer "${file.name}".`,
            timestamp: new Date().toISOString(),
            status: 'pending',
            targetPatientId: patientId,
            initiatorName: `Dr. ${user.firstName} ${user.lastName}`,
            payload: { fileId: file.id },
          });
          const updated = await getNotifications(user.id);
          setNotifications(updated);
        },
      });
    } else {
      modal.confirm({
        title: 'Supprimer ce fichier ?',
        content: `Êtes-vous sûr de vouloir supprimer "${file.name}" ? Cette action est irréversible.`,
        okText: 'Supprimer',
        okType: 'danger',
        cancelText: 'Annuler',
        onOk: async () => {
          await deleteFile(file.id);
          loadFiles();
        },
      });
    }
  };

  const renderFileViewer = () => {
    if (!viewingFile) return null;
    const { type, url, name } = viewingFile;

    if (type.startsWith('image/')) {
      return <img src={url ?? ''} alt={name} style={{ maxWidth: '100%', maxHeight: '70vh' }} />;
    }
    if (type === 'application/pdf') {
      return <iframe src={url ?? ''} title={name} style={{ width: '100%', height: '70vh', border: 'none' }} />;
    }
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <p>Aperçu non disponible pour ce type de fichier.</p>
        <Button type="primary" href={url ?? '#'} download={name}>
          Télécharger
        </Button>
      </div>
    );
  };

  const uploadProps = {
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList: list }: { fileList: UploadFile[] }) => setFileList(list.slice(-1)),
    maxCount: 1,
  };

  const columns: ColumnsType<MedicalFile> = [
    { title: 'Nom', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: 'Date', dataIndex: 'date', key: 'date', width: 120 },
    { title: 'Type', dataIndex: 'type', key: 'type', width: 160, ellipsis: true },
    { title: 'Ajouté par', dataIndex: 'uploaderName', key: 'uploaderName' },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      render: (_, file) => (
        <Space>
          <Button size="small" onClick={() => setViewingFile(file)}>Voir</Button>
          <Button size="small" onClick={() => { setReplaceTarget(file); setFileList([]); }}>Remplacer</Button>
          <Button size="small" danger onClick={() => handleDelete(file)}>Supprimer</Button>
        </Space>
      ),
    },
  ];

  // Pending notifications in store (for informational banner)
  const pendingFileNotifs = notifications.filter(
    (n) => (n.type === 'file_upload' || n.type === 'file_edit' || n.type === 'file_delete') &&
           n.status === 'pending' &&
           n.targetPatientId === patientId
  );

  return (
    <div className={style.container}>
      <div className={style.header}>
        <Title level={2} style={{ margin: 0 }}>Mon dossier médical</Title>
        <Button type="primary" onClick={() => { setUploadVisible(true); setFileList([]); }}>
          Téléverser un fichier
        </Button>
      </div>

      {isDoctor && pendingFileNotifs.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message={`${pendingFileNotifs.length} action(s) en attente d'approbation du patient.`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Table
        columns={columns}
        dataSource={files}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: 'Aucun fichier dans le dossier' }}
      />

      {/* File viewer modal */}
      <Modal
        title={viewingFile?.name}
        open={!!viewingFile}
        onCancel={() => setViewingFile(null)}
        footer={null}
        width={800}
      >
        {renderFileViewer()}
      </Modal>

      {/* Upload modal */}
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
            disabled={fileList.length === 0}
            onClick={handleUpload}
          >
            {isDoctor ? 'Envoyer la demande' : 'Téléverser'}
          </Button>,
        ]}
      >
        {isDoctor && (
          <Alert
            type="info"
            showIcon
            message="En tant que médecin, votre téléversement nécessite l'approbation du patient."
            style={{ marginBottom: 16 }}
          />
        )}
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">Cliquez ou glissez un fichier ici</p>
          <p className="ant-upload-hint">Formats supportés : PDF, images, documents</p>
        </Dragger>
      </Modal>

      {/* Replace modal */}
      <Modal
        title={`Remplacer "${replaceTarget?.name ?? ''}"`}
        open={!!replaceTarget}
        onCancel={() => setReplaceTarget(null)}
        footer={[
          <Button key="cancel" onClick={() => setReplaceTarget(null)}>Annuler</Button>,
          <Button
            key="replace"
            type="primary"
            loading={uploading}
            disabled={fileList.length === 0}
            onClick={handleReplace}
          >
            {isDoctor ? 'Envoyer la demande' : 'Remplacer'}
          </Button>,
        ]}
      >
        {isDoctor && (
          <Alert
            type="info"
            showIcon
            message="En tant que médecin, votre modification nécessite l'approbation du patient."
            style={{ marginBottom: 16 }}
          />
        )}
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">Glissez le fichier de remplacement ici</p>
        </Dragger>
      </Modal>
    </div>
  );
};

export default Dossier;
