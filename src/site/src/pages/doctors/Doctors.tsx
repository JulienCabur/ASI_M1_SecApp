import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Input,
  List,
  Modal,
  Space,
  Table,
  Typography,
  App,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useAuth } from '@/hooks/useAuth';
import { useNotificationsStore } from '@/store/notifications.store';
import {
  getDoctors,
  searchDoctors,
  addDoctor,
  removeDoctor,
} from '@/services/doctors.service';
import { resolveNotification } from '@/services/notifications.service';
import type { Doctor, Notification } from '@/types';
import style from './doctors.module.scss';

const { Title } = Typography;
const { Search } = Input;

const Doctors: React.FC = () => {
  const { user } = useAuth();
  const { modal } = App.useApp();
  const { notifications, resolve } = useNotificationsStore();
  const patientId = user?.id ?? 'mock-patient';

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchResults, setSearchResults] = useState<Doctor[]>([]);
  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  // Pending doctor_add notifications directed at this patient
  const pendingDoctorAdds = notifications.filter(
    (n) => n.type === 'doctor_add' && n.status === 'pending' && n.targetPatientId === patientId
  );

  const loadDoctors = () => {
    setLoading(true);
    getDoctors(patientId)
      .then(setDoctors)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDoctors();
  }, [patientId]);

  const handleSearch = (value: string) => {
    if (!value.trim()) {
      setSearchResults([]);
      return;
    }
    searchDoctors(value).then(setSearchResults);
  };

  const handleAddDoctor = async () => {
    if (!selectedDoctor) return;
    setAddLoading(true);
    await addDoctor(patientId, selectedDoctor.id);
    setAddLoading(false);
    setSearchVisible(false);
    setSelectedDoctor(null);
    setSearchResults([]);
    loadDoctors();
  };

  const handleRemove = (doctor: Doctor) => {
    modal.confirm({
      title: 'Supprimer ce médecin ?',
      content: `Êtes-vous sûr de vouloir retirer Dr. ${doctor.firstName} ${doctor.lastName} de vos médecins ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        await removeDoctor(patientId, doctor.id);
        loadDoctors();
      },
    });
  };

  const handleResolveNotification = async (notif: Notification, decision: 'approved' | 'rejected') => {
    await resolveNotification(notif.id, decision);
    resolve(notif.id, decision);
  };

  const columns: ColumnsType<Doctor> = [
    {
      title: 'Nom',
      key: 'name',
      render: (_, doc) => `Dr. ${doc.firstName} ${doc.lastName}`,
    },
    {
      title: 'Spécialité',
      dataIndex: 'specialty',
      key: 'specialty',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, doc) => (
        <Button danger size="small" onClick={() => handleRemove(doc)}>
          Supprimer
        </Button>
      ),
    },
  ];

  return (
    <div className={style.container}>
      <div className={style.header}>
        <Title level={2} style={{ margin: 0 }}>Mes médecins</Title>
        <Button type="primary" onClick={() => setSearchVisible(true)}>
          Ajouter un médecin
        </Button>
      </div>

      {/* Pending doctor_add approval requests */}
      {pendingDoctorAdds.map((notif) => (
        <Alert
          key={notif.id}
          type="info"
          showIcon
          message={notif.description}
          style={{ marginBottom: 12 }}
          action={
            <Space>
              <Button
                size="small"
                type="primary"
                onClick={() => handleResolveNotification(notif, 'approved')}
              >
                Approuver
              </Button>
              <Button
                size="small"
                danger
                onClick={() => handleResolveNotification(notif, 'rejected')}
              >
                Refuser
              </Button>
            </Space>
          }
        />
      ))}

      <Table
        columns={columns}
        dataSource={doctors}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: 'Aucun médecin assigné' }}
      />

      {/* Add doctor search modal */}
      <Modal
        title="Ajouter un médecin"
        open={searchVisible}
        onCancel={() => {
          setSearchVisible(false);
          setSelectedDoctor(null);
          setSearchResults([]);
        }}
        footer={[
          <Button key="cancel" onClick={() => setSearchVisible(false)}>
            Annuler
          </Button>,
          <Button
            key="add"
            type="primary"
            disabled={!selectedDoctor}
            loading={addLoading}
            onClick={handleAddDoctor}
          >
            Ajouter
          </Button>,
        ]}
      >
        <Search
          placeholder="Rechercher par nom ou spécialité..."
          onSearch={handleSearch}
          onChange={(e) => handleSearch(e.target.value)}
          style={{ marginBottom: 16 }}
        />
        <List
          dataSource={searchResults}
          locale={{ emptyText: 'Aucun résultat' }}
          renderItem={(doc) => (
            <List.Item
              className={selectedDoctor?.id === doc.id ? style.selected : style.listItem}
              onClick={() => setSelectedDoctor(doc)}
              style={{ cursor: 'pointer' }}
            >
              <List.Item.Meta
                title={`Dr. ${doc.firstName} ${doc.lastName}`}
                description={doc.specialty}
              />
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
};

export default Doctors;
