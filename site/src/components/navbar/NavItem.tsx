import style from './navbar.module.scss';
import { useNavigate } from 'react-router';
import { FaHome, FaFolderOpen } from 'react-icons/fa';
import { FaSignOutAlt } from 'react-icons/fa';


export const NavItem = ( { label, to }: { label: string; to: string }) => {
    const navigate = useNavigate();
    switch (label) {
        case 'Home':
            return (
                <div className={style.navItem} onClick={() => navigate(to)}>
                    <FaHome className={style.icon} />
                </div>
            );
        case 'Folders':
            return (
                <div className={style.navItem} onClick={() => navigate(to)}>
                    <FaFolderOpen className={style.icon} />
                </div>
            );
        case 'Logout':
            return (
                <div className={style.navItem} onClick={() => {
                    localStorage.removeItem('access_token');
                    navigate("/login");}}>
                    <FaSignOutAlt className={style.icon} />
                </div>
            );
        default:
            return (
                <div onClick={() => navigate(to)}>{label}</div>
            );
    }
};
