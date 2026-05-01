import { useEffect, useState } from 'react';
import { Card, Col, Row, List, Typography, Badge, Button } from 'antd';
import { useNavigate } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import { useNotificationsStore } from '@/store/notifications.store';
import { getDoctors } from '@/services/doctors.service';
import { listFiles, type RemoteFile } from '@/services/files.service';
import { getNotifications } from '@/services/notifications.service';
import type { Doctor } from '@/types';
import style from './dashboard.module.scss';

const { Title, Text } = Typography;

const PatientDashboard: React.FC = () => {
  const { user } = useAuth();
  const { pendingCount, setNotifications } = useNotificationsStore();
  const navigate = useNavigate();

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [recentFiles, setRecentFiles] = useState<RemoteFile[]>([]);

  const patientId = user?.id ?? 'mock-patient';

  useEffect(() => {
    getDoctors(patientId).then(setDoctors);
    listFiles()
      .then((files) => setRecentFiles(files.slice(-3).reverse()))
      .catch(() => setRecentFiles([]));
    getNotifications(patientId).then(setNotifications);
  }, [patientId, setNotifications]);

  return (
    <div className={style.dashboard}>
      <Title level={2}>Bonjour, {user?.firstName ?? 'Patient'}</Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} md={8}>
          <Card
            title="Mes médecins"
            extra={<Button type="link" onClick={() => navigate('/doctors')}>Voir tout</Button>}
            className={style.card}
          >
            <div className={style.stat}>{doctors.length}</div>
            <Text type="secondary">médecin{doctors.length !== 1 ? 's' : ''} assigné{doctors.length !== 1 ? 's' : ''}</Text>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            title="Fichiers récents"
            extra={<Button type="link" onClick={() => navigate('/dossier')}>Voir tout</Button>}
            className={style.card}
          >
            {recentFiles.length === 0 ? (
              <Text type="secondary">Aucun fichier</Text>
            ) : (
              <List
                size="small"
                dataSource={recentFiles}
                renderItem={(file) => (
                  <List.Item>
                    <Text ellipsis style={{ maxWidth: 160 }}>{file.name}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{file.date}</Text>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            title="Notifications en attente"
            extra={<Button type="link" onClick={() => navigate('/notifications')}>Voir tout</Button>}
            className={style.card}
          >
            <Badge count={pendingCount} overflowCount={99}>
              <div className={style.stat}>{pendingCount}</div>
            </Badge>
            <Text type="secondary">action{pendingCount !== 1 ? 's' : ''} en attente</Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PatientDashboard;
