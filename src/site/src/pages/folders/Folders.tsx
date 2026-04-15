
import { Typography } from "antd";
import style from "./folders.module.scss";

const { Title } = Typography;

const Folders: React.FC = () => {
    return (
        <div className={style.foldersContainer}>
            <Title level={2} className={style.title}>Dossiers</Title>

        </div>
    );
}
export default Folders;