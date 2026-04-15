import { useEffect } from 'react';
import { Button, Empty, List, Space, Tag, Typography } from 'antd';
import { useAuth } from '@/hooks/useAuth';
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
  file_upload: 'Téléversement',
  file_edit: 'Modification',
  file_delete: 'Suppression',
  doctor_add: 'Accès médecin',
};

const Notifications: React.FC = () => {
  const { user } = useAuth();
  const { notifications, setNotifications, resolve } = useNotificationsStore();

  const userId = user?.id ?? 'mock-patient';

  useEffect(() => {
    getNotifications(userId).then(setNotifications);
  }, [userId, setNotifications]);

  const handleResolve = async (id: string, decision: 'approved' | 'rejected') => {
    await resolveNotification(id, decision);
    resolve(id, decision);
  };

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));

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
            <List.Item
              key={notif.id}
              className={style.item}
              extra={
                notif.status === 'pending' ? (
                  <Space>
                    <Button
                      type="primary"
                      size="small"
                      onClick={() => handleResolve(notif.id, 'approved')}
                    >
                      Approuver
                    </Button>
                    <Button
                      danger
                      size="small"
                      onClick={() => handleResolve(notif.id, 'rejected')}
                    >
                      Refuser
                    </Button>
                  </Space>
                ) : (
                  <Tag color={statusColor[notif.status]}>{statusLabel[notif.status]}</Tag>
                )
              }
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Tag>{typeLabel[notif.type]}</Tag>
                    <Text strong>{notif.initiatorName}</Text>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={2}>
                    <Text>{notif.description}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{formatDate(notif.timestamp)}</Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  );
};

export default Notifications;
