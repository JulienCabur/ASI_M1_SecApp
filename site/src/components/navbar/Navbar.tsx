
import style from './navbar.module.scss';
import { NavItem } from './NavItem';

const Navbar = () => {

    return (
        <div className={style.navbar}>
            <div className={style.links}>
                <NavItem label="Home" to="/" />
                <NavItem label="Folders" to="/folders" />
                <NavItem label="Logout" to="/logout" />
            </div>
        </div>
    );
};
export default Navbar;