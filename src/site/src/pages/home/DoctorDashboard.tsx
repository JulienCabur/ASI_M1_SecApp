import { useEffect } from 'react';
import { Card, Col, Row, List, Typography, Button } from 'antd';
import { useNavigate } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import { useNotificationsStore } from '@/store/notifications.store';
import { getNotifications } from '@/services/notifications.service';
import style from './dashboard.module.scss';

const { Title, Text } = Typography;

const DoctorDashboard: React.FC = () => {
  const { user } = useAuth();
  const { pendingCount, notifications, setNotifications } = useNotificationsStore();
  const navigate = useNavigate();

  const userId = user?.id ?? 'mock-doctor';

  useEffect(() => {
    getNotifications().then(setNotifications).catch(() => setNotifications([]));
  }, [userId, setNotifications]);

  const recentActivity = notifications.slice(0, 3);

  return (
    <div className={style.dashboard}>
      <Title level={2}>Bonjour, Dr. {user?.lastName ?? 'Médecin'}</Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} md={8}>
          <Card title="Mes patients" className={style.card}>
            <div className={style.stat}>–</div>
            <Text type="secondary">patients assignés</Text>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            title="Approbations en attente"
            extra={<Button type="link" onClick={() => navigate('/notifications')}>Voir tout</Button>}
            className={style.card}
          >
            <div className={style.stat}>{pendingCount}</div>
            <Text type="secondary">approbation{pendingCount !== 1 ? 's' : ''} en attente</Text>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="Activité récente" className={style.card}>
            {recentActivity.length === 0 ? (
              <Text type="secondary">Aucune activité récente</Text>
            ) : (
              <List
                size="small"
                dataSource={recentActivity}
                renderItem={(notif) => (
                  <List.Item>
                    <Text ellipsis style={{ maxWidth: 200, fontSize: 13 }}>{notif.description}</Text>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DoctorDashboard;
