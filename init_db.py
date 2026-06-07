import mysql.connector

def init_database():
    # Connect to MySQL server
    db = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="Tanu@123"
    )
    cursor = db.cursor()

    # Create Database
    cursor.execute("CREATE DATABASE IF NOT EXISTS goparky")
    print("Database 'goparky' created or already exists.")

    # Reconnect specifically to goparky database
    db.database = "goparky"

    # Define tables in correct order of creation (dependencies first)
    tables = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                role VARCHAR(10) NOT NULL,
                gender ENUM('male','female') NOT NULL,
                contact VARCHAR(15) NOT NULL,
                email VARCHAR(50) NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        """,
        "vehicle": """
            CREATE TABLE IF NOT EXISTS vehicle (
                vehicle_id VARCHAR(20) PRIMARY KEY,
                owner VARCHAR(30) NOT NULL,
                contact VARCHAR(15) NOT NULL,
                type VARCHAR(5) NOT NULL
            )
        """,
        "parkslot": """
            CREATE TABLE IF NOT EXISTS parkslot (
                slot_id VARCHAR(5) PRIMARY KEY,
                status ENUM('available','occupied','not-available') NOT NULL
            )
        """,
        "parklog": """
            CREATE TABLE IF NOT EXISTS parklog (
                log_id INT PRIMARY KEY AUTO_INCREMENT,
                vehicle_id VARCHAR(20) NOT NULL,
                slot_id VARCHAR(5) NOT NULL,
                entry_time DATETIME NOT NULL,
                exit_time DATETIME,
                payment DECIMAL(10,2),
                id INT,
                FOREIGN KEY (slot_id) REFERENCES parkslot(slot_id),
                FOREIGN KEY (id) REFERENCES users(id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicle(vehicle_id)
            )
        """,
        "staff_logins": """
            CREATE TABLE IF NOT EXISTS staff_logins (
                slno INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
    }

    for name, ddl in tables.items():
        cursor.execute(ddl)
        print(f"Table '{name}' initialized.")

    # Insert default admin user if not exists
    cursor.execute("SELECT id FROM users WHERE name = 'Shri'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (id, name, role, gender, contact, email, password)
            VALUES (1, 'Shri', 'Admin', 'female', '7894561230', 'shri@gmail.com', 'Shri*12345')
        """)
        db.commit()
        print("Default admin user 'Shri' inserted.")

    # Insert default slots if not exist
    cursor.execute("SELECT COUNT(*) FROM parkslot")
    if cursor.fetchone()[0] == 0:
        # B1-B36
        b_slots = [(f"B{i}", "available") for i in range(1, 37)]
        # C1-C52
        c_slots = [(f"C{i}", "available") for i in range(1, 53)]
        all_slots = b_slots + c_slots

        cursor.executemany(
            "INSERT INTO parkslot (slot_id, status) VALUES (%s, %s)",
            all_slots
        )
        db.commit()
        print(f"Inserted {len(all_slots)} parking slots (B1-B36, C1-C52).")

    cursor.close()
    db.close()
    print("Database initialization completed successfully.")

if __name__ == "__main__":
    init_database()
