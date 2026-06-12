import { useEffect, useState } from 'react';
import { App, Button, Form, Input, Modal, Space, Table, Tooltip, Typography } from 'antd';
import { useNavigate } from 'react-router';
import type { ColumnsType } from 'antd/es/table';
import {
  doctorAddPatient,
  doctorRemovePatient,
  findPatientByUsername,
  getRelations,
  type RelationSummary,
} from '@/services/relation.service';
import { ApiError } from '@/services/api';
import style from './patients.module.scss';

const { Title } = Typography;

const Patients: React.FC = () => {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();

  const [relations, setRelations] = useState<RelationSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [addVisible, setAddVisible] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  const [form] = Form.useForm<{ username: string }>();

  const load = async () => {
    setLoading(true);
    try {
      const rels = await getRelations();
      setRelations(rels);
    } catch (err) {
      console.error('[Patients] load error:', err);
      void message.error('Impossible de charger les patients.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleAdd = async () => {
    let values: { username: string };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setAddLoading(true);
    try {
      const patient = await findPatientByUsername(values.username.trim());
      await doctorAddPatient(patient.id);
      void message.success(
        `Patient "${patient.username}" ajouté. En attente de vérification.`,
      );
      form.resetFields();
      setAddVisible(false);
      await load();
    } catch (err) {
      console.error('[Patients] add error:', err);
      if (err instanceof ApiError && err.status === 404) {
        void message.error(`Aucun patient trouvé avec ce username.`);
      } else {
        void message.error("Erreur lors de l'ajout du patient.");
      }
    } finally {
      setAddLoading(false);
    }
  };

  const handleRemove = (row: RelationSummary) => {
    modal.confirm({
      title: 'Retirer ce patient ?',
      content: `Êtes-vous sûr de vouloir retirer ${row.username} de vos patients ?`,
      okText: 'Retirer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await doctorRemovePatient(row.counterpart_id);
          void message.success('Patient retiré.');
          await load();
        } catch (err) {
          console.error('[Patients] remove error:', err);
          void message.error('Erreur lors de la suppression.');
        }
      },
    });
  };

  const openDossier = (row: RelationSummary) => {
    const params = new URLSearchParams({
      patient: row.counterpart_id,
      name: row.username,
    });
    navigate(`/dossier?${params.toString()}`);
  };

  const columns: ColumnsType<RelationSummary> = [
    {
      title: 'Patient',
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
        <Space>
          <Tooltip title={row.is_verified ? '' : 'Patient non encore vérifié'}>
            <Button
              size="small"
              type="primary"
              disabled={!row.is_verified}
              onClick={() => openDossier(row)}
            >
              Voir dossier
            </Button>
          </Tooltip>
          <Button danger size="small" onClick={() => handleRemove(row)}>
            Retirer
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className={style.container}>
      <div className={style.header}>
        <Title level={2} style={{ margin: 0 }}>Mes patients</Title>
        <Button type="primary" onClick={() => setAddVisible(true)}>
          Ajouter un patient
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={relations}
        rowKey="counterpart_id"
        loading={loading}
        locale={{ emptyText: 'Aucun patient assigné' }}
      />

      <Modal
        title="Ajouter un patient"
        open={addVisible}
        onCancel={() => {
          setAddVisible(false);
          form.resetFields();
        }}
        onOk={handleAdd}
        okText="Ajouter"
        cancelText="Annuler"
        confirmLoading={addLoading}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="Username du patient"
            name="username"
            rules={[{ required: true, message: 'Veuillez entrer le username' }]}
          >
            <Input placeholder="ex: alice.dupont" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Patients;
