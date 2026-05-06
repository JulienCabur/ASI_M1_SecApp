import { useEffect, useMemo, useState } from 'react';
import {
  App,
  Button,
  Input,
  List,
  Modal,
  Table,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  getRelations,
  listDoctors,
  patientAddDoctor,
  patientRemoveDoctor,
  type RelationSummary,
  type RelationUser,
} from '@/services/relation.service';
import style from './doctors.module.scss';

const { Title } = Typography;
const { Search } = Input;

const Doctors: React.FC = () => {
  const { message, modal } = App.useApp();

  const [doctorsCatalog, setDoctorsCatalog] = useState<RelationUser[]>([]);
  const [myDoctors, setMyDoctors] = useState<RelationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDoctor, setSelectedDoctor] = useState<RelationUser | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [docs, rels] = await Promise.all([listDoctors(), getRelations()]);
      setDoctorsCatalog(docs);
      setMyDoctors(rels);
    } catch (err) {
      console.error('[Doctors] load error:', err);
      void message.error('Impossible de charger les médecins.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const myDoctorIds = new Set(myDoctors.map((d) => d.counterpart_id));
    const available = doctorsCatalog.filter((d) => !myDoctorIds.has(d.id));
    if (!q) return available;
    return available.filter((d) => d.username.toLowerCase().includes(q));
  }, [searchQuery, doctorsCatalog, myDoctors]);

  const handleAddDoctor = async () => {
    if (!selectedDoctor) return;
    setAddLoading(true);
    try {
      await patientAddDoctor(selectedDoctor.id);
      void message.success(`Médecin "${selectedDoctor.username}" ajouté.`);
      setSearchVisible(false);
      setSelectedDoctor(null);
      setSearchQuery('');
      await loadAll();
    } catch (err) {
      console.error('[Doctors] add error:', err);
      void message.error("Erreur lors de l'ajout du médecin.");
    } finally {
      setAddLoading(false);
    }
  };

  const handleRemove = (row: RelationSummary) => {
    modal.confirm({
      title: 'Supprimer ce médecin ?',
      content: `Êtes-vous sûr de vouloir retirer ${row.username} de vos médecins ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await patientRemoveDoctor(row.counterpart_id);
          void message.success('Médecin retiré.');
          await loadAll();
        } catch (err) {
          console.error('[Doctors] remove error:', err);
          void message.error('Erreur lors de la suppression.');
        }
      },
    });
  };

  const columns: ColumnsType<RelationSummary> = [
    {
      title: 'Médecin',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: 'Statut',
      key: 'verified',
      render: (_, row) => (row.is_verified ? 'Vérifié' : 'En attente'),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, row) => (
        <Button danger size="small" onClick={() => handleRemove(row)}>
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

      <Table
        columns={columns}
        dataSource={myDoctors}
        rowKey="counterpart_id"
        loading={loading}
        locale={{ emptyText: 'Aucun médecin assigné' }}
      />

      <Modal
        title="Ajouter un médecin"
        open={searchVisible}
        onCancel={() => {
          setSearchVisible(false);
          setSelectedDoctor(null);
          setSearchQuery('');
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
          placeholder="Rechercher par username..."
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ marginBottom: 16 }}
          allowClear
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
              <List.Item.Meta title={doc.username} />
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
};

export default Doctors;
