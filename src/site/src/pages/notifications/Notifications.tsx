import { useEffect, useState } from 'react';
import { App, Button, Empty, List, Space, Tag, Typography } from 'antd';
import { useNotificationsStore } from '@/store/notifications.store';
import { getNotifications, resolveNotification } from '@/services/notifications.service';
import type { Notification, NotificationStatus } from '@/types';
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

const Notifications: React.FC = () => {
  const { message } = App.useApp();
  const { notifications, setNotifications, resolve } = useNotificationsStore();
  const [pendingId, setPendingId] = useState<string | null>(null);

  const reload = async () => {
    try {
      const list = await getNotifications();
      setNotifications(list);
    } catch (err) {
      console.error('[Notifications] load error:', err);
      void message.error('Impossible de charger les notifications.');
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
      // Rafraîchir pour retirer la notif résolue de la liste.
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

  return (
    <div className={style.container}>
      <Title level={2}>Notifications</Title>

      {notifications.length === 0 ? (
        <Empty description="Aucune notification" />
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
    </div>
  );
};

export default Notifications;
