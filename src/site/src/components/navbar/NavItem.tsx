import { Modal } from 'antd';
import {
  FaBell,
  FaFolderOpen,
  FaHome,
  FaMobileAlt,
  FaSignOutAlt,
  FaUserInjured,
  FaUserMd,
  FaUserSlash,
} from 'react-icons/fa';
import { FaFileMedical } from 'react-icons/fa6';
import { useNavigate } from 'react-router';
import { deleteAccount, logout } from '@/services/auth.service';
import style from './navbar.module.scss';

export const NavItem = ({ label, to }: { label: string; to: string }) => {
  const navigate = useNavigate();

  switch (label) {
    case 'Home':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaHome className={style.icon} />
        </div>
      );
    case 'Dossier':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaFileMedical className={style.icon} />
        </div>
      );
    case 'Doctors':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaUserMd className={style.icon} />
        </div>
      );
    case 'Patients':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaUserInjured className={style.icon} />
        </div>
      );
    case 'Notifications':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaBell className={style.icon} />
        </div>
      );
    case 'Folders':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaFolderOpen className={style.icon} />
        </div>
      );
    case 'Devices':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaMobileAlt className={style.icon} />
        </div>
      );
    case 'Logout':
      return (
        <div
          className={style.navItem}
          onClick={() => {
            void logout();
          }}
        >
          <FaSignOutAlt className={style.icon} />
        </div>
      );
    case 'DeleteAccount':
      return (
        <div
          className={`${style.navItem} ${style.navItemDanger}`}
          onClick={() => {
            Modal.confirm({
              title: 'Supprimer mon compte',
              content:
                'Cette action est irréversible. Toutes vos données (fichiers, appareils, relations) seront définitivement effacées.',
              okText: 'Supprimer',
              okButtonProps: { danger: true },
              cancelText: 'Annuler',
              onOk: async () => {
                await deleteAccount();
                void logout();
              },
            });
          }}
        >
          <FaUserSlash className={style.icon} />
        </div>
      );
    default:
      return (
        <div onClick={() => navigate(to)}>{label}</div>
      );
  }
};
