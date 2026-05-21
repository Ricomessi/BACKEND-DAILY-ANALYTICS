import psycopg2

# Gunakan konfigurasi Cloud SQL kamu (sama seperti sebelumnya)
DB_CONFIG = {
    "user": "postgres",
    "password": "~jr}J]0k1~,7e+]O",
    "database": "mbasystem",
    "host": "34.59.60.237",
    "port": "5432"
}

def create_anomaly_table():
    try:
        # Koneksi ke Cloud SQL dari laptopmu
        print("Menghubungkan ke Cloud SQL...")
        # Tambahkan sslmode='require' jika Cloud SQL kamu mewajibkan SSL
        conn = psycopg2.connect(**DB_CONFIG, sslmode='require')
        cur = conn.cursor()

        # 1. Query untuk membuat tabel (IF NOT EXISTS mencegah error jika tabel sudah ada)
        create_table_query = """
        CREATE TABLE IF NOT EXISTS anomaly_rules (
            id SERIAL PRIMARY KEY,
            field VARCHAR(50) NOT NULL,
            operator VARCHAR(10) NOT NULL,
            value VARCHAR(255) NOT NULL,
            min_duration INT DEFAULT 0,
            severity VARCHAR(20) NOT NULL,
            rule_type VARCHAR(50) NOT NULL,
            message VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
        """
        print("Mengeksekusi pembuatan tabel...")
        cur.execute(create_table_query)

        # 2. Masukkan 1 data awal sebagai contoh (Fallen Detection)
        # Cek dulu apakah tabel masih kosong agar tidak duplikat saat script dijalankan 2x
        cur.execute("SELECT COUNT(*) FROM anomaly_rules")
        count = cur.fetchone()[0]

        if count == 0:
            insert_query = """
            INSERT INTO anomaly_rules (field, operator, value, severity, rule_type, message) 
            VALUES ('yolo_action', '==', 'Fallen / Lying', 'high', 'Safety', 'Fallen detected on {cam}');
            """
            cur.execute(insert_query)
            print("Data awal (Rule Fallen) berhasil ditambahkan.")
        else:
            print("Tabel sudah berisi data, melewati proses insert.")

        # WAJIB COMMIT agar perubahan disimpan permanen di database
        conn.commit()
        
        cur.close()
        conn.close()
        print("✅ Sukses! Tabel anomaly_rules siap digunakan di Cloud SQL.")

    except Exception as e:
        print("❌ Terjadi kesalahan:", e)

if __name__ == '__main__':
    create_anomaly_table()