CREATE DATABASE inbox DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON inbox.* to 'inbox'@'localhost' IDENTIFIED BY 'root';

CREATE DATABASE test DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON test.* to 'inboxtest'@'localhost' IDENTIFIED BY 'root';