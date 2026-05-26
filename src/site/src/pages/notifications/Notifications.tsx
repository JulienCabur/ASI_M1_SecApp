import { useEffect, useState } from 'react';
import { App, Button, Divider, Empty, List, Space, Tag, Typography } from 'antd';
import { useNotificationsStore } from '@/store/notifications.store';
import {
  getFilePendingRequests,
  getNotifications,
  resolveNotification,
} from '@/services/notifications.service';
import { validateRequest, rejectRequest } from '@/services/files.service';
import type { Notification, NotificationStatus, PendingFileRequest } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import style from './notifications.module.scss';

const { Title, Text } = Typography;

const statusColor: Record<NotificationStatus, string> = {
  pending: 'processing',
  approved: 'success',
  rejected: 'error',
};

const statusLabel: Record<NotificationStatus, string> = {
  pending: 'En attente',
  approved: 'Approuvé',
  rejected: 'Refusé',
};

const typeLabel: Record<Notification['type'], string> = {
  doctor_add: 'Accès médecin',
  patient_add: 'Demande envoyée',
};

const fileOperationLabel: Record<PendingFileRequest['operationType'], string> = {
  create: 'Ajout proposé',
  update: 'Modification proposée',
  delete: 'Suppression proposée',
};

const fileOperationColor: Record<PendingFileRequest['operationType'], string> = {
  create: 'green',
  update: 'blue',
  delete: 'red',
};

const Notifications: React.FC = () => {
  const { message } = App.useApp();
  const { role } = useAuth();
  const { notifications, setNotifications, setFileRequests, resolve } = useNotificationsStore();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [fileRequests, setLocalFileRequests] = useState<PendingFileRequest[]>([]);
  const [fileActionId, setFileActionId] = useState<string | null>(null);
  const isPatient = role === 'role_patients';

  const reload = async () => {
    try {
      const list = await getNotifications();
      setNotifications(list);
    } catch (err) {
      console.error('[Notifications] load error:', err);
      void message.error('Impossible de charger les notifications.');
    }
    if (isPatient) {
      try {
        const fileList = await getFilePendingRequests();
        setLocalFileRequests(fileList);
        setFileRequests(fileList);
      } catch (err) {
        console.error('[Notifications] file requests error:', err);
      }
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const handleResolve = async (notif: Notification, decision: 'approved' | 'rejected') => {
    setPendingId(notif.id);
    try {
      await resolveNotification(notif, decision);
      resolve(notif.id, decision);
      void message.success(decision === 'approved' ? 'Demande approuvée.' : 'Demande refusée.');
      void reload();
    } catch (err) {
      console.error('[Notifications] resolve error:', err);
      const msg = err instanceof Error ? err.message : 'Erreur lors du traitement.';
      void message.error(msg);
    } finally {
      setPendingId(null);
    }
  };

  const renderActions = (notif: Notification) => {
    if (notif.status !== 'pending') {
      return <Tag color={statusColor[notif.status]}>{statusLabel[notif.status]}</Tag>;
    }
    if (notif.direction === 'outgoing') {
      return (
        <Button
          danger
          size="small"
          loading={pendingId === notif.id}
          disabled={pendingId !== null && pendingId !== notif.id}
          onClick={() => handleResolve(notif, 'rejected')}
        >
          Annuler
        </Button>
      );
    }
    return (
      <Space>
        <Button
          type="primary"
          size="small"
          loading={pendingId === notif.id}
          disabled={pendingId !== null && pendingId !== notif.id}
          onClick={() => handleResolve(notif, 'approved')}
        >
          Approuver
        </Button>
        <Button
          danger
          size="small"
          disabled={pendingId !== null}
          onClick={() => handleResolve(notif, 'rejected')}
        >
          Refuser
        </Button>
      </Space>
    );
  };

  const handleFileValidate = async (req: PendingFileRequest) => {
    setFileActionId(req.fileRequestId);
    try {
      await validateRequest(req.fileRequestId);
      void message.success('Demande approuvée.');
      const updated = fileRequests.filter((r) => r.fileRequestId !== req.fileRequestId);
      setLocalFileRequests(updated);
      setFileRequests(updated);
    } catch (err) {
      void message.error(`Approbation impossible : ${(err as Error).message}`);
    } finally {
      setFileActionId(null);
    }
  };

  const handleFileReject = async (req: PendingFileRequest) => {
    setFileActionId(req.fileRequestId);
    try {
      await rejectRequest(req.fileRequestId);
      void message.success('Demande refusée.');
      const updated = fileRequests.filter((r) => r.fileRequestId !== req.fileRequestId);
      setLocalFileRequests(updated);
      setFileRequests(updated);
    } catch (err) {
      void message.error(`Refus impossible : ${(err as Error).message}`);
    } finally {
      setFileActionId(null);
    }
  };

  return (
    <div className={style.container}>
      <Title level={2}>Notifications</Title>

      {notifications.length === 0 ? (
        <Empty description="Aucune notification de relation" />
      ) : (
        <List
          itemLayout="vertical"
          dataSource={notifications}
          renderItem={(notif) => (
            <List.Item key={notif.id} className={style.item} extra={renderActions(notif)}>
              <List.Item.Meta
                title={
                  <Space>
                    <Tag>{typeLabel[notif.type]}</Tag>
                    <Text strong>{notif.initiatorName}</Text>
                  </Space>
                }
                description={<Text>{notif.description}</Text>}
              />
            </List.Item>
          )}
        />
      )}

      {isPatient && (
        <>
          <Divider />
          <Title level={3}>Fichiers en attente</Title>
          {fileRequests.length === 0 ? (
            <Empty description="Aucune demande de fichier en attente" />
          ) : (
            <List
              itemLayout="vertical"
              dataSource={fileRequests}
              renderItem={(req) => (
                <List.Item
                  key={req.fileRequestId}
                  className={style.item}
                  extra={
                    <Space>
                      <Button
                        type="primary"
                        size="small"
                        loading={fileActionId === req.fileRequestId}
                        disabled={fileActionId !== null && fileActionId !== req.fileRequestId}
                        onClick={() => handleFileValidate(req)}
                      >
                        Approuver
                      </Button>
                      <Button
                        danger
                        size="small"
                        disabled={fileActionId !== null}
                        onClick={() => handleFileReject(req)}
                      >
                        Refuser
                      </Button>
                    </Space>
                  }
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color={fileOperationColor[req.operationType]}>
                          {fileOperationLabel[req.operationType]}
                        </Tag>
                        <Text strong>{req.fileName}</Text>
                      </Space>
                    }
                    description={<Text type="secondary">{req.date}</Text>}
                  />
                </List.Item>
              )}
            />
          )}
        </>
      )}
    </div>
  );
};

export default Notifications;
