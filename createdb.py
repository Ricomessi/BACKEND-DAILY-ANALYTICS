import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

# ─── KONFIGURASI SERVER ───
# Masukkan IP Cloud SQL kamu yang baru di sini
DB_HOST = os.environ.get("DB_HOST", "136.119.162.109")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "DezYnNbD\~2\S:|5")
DB_PORT = os.environ.get("DB_PORT", "5432")
TARGET_DB = "mbabatch2"

def setup_database():
    # 1. Bikin Database 'mbasystem'
    try:
        print("⏳ Konek ke database default 'postgres'...")
        # Konek ke default db dulu karena mbasystem belum ada
        conn = psycopg2.connect(dbname='postgres', user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
        
        # Wajib diset autocommit untuk perintah CREATE DATABASE
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) 
        cur = conn.cursor()
        
        # Cek apakah DB sudah ada biar ga error kalau dijalankan 2x
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{TARGET_DB}'")
        exists = cur.fetchone()
        
        if not exists:
            print(f"🔨 Membuat database '{TARGET_DB}'...")
            cur.execute(f"CREATE DATABASE {TARGET_DB};")
            print("✅ Database berhasil dibuat!")
        else:
            print(f"⚡ Database '{TARGET_DB}' sudah ada, lanjut bikin tabel...")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Gagal bikin database: {e}")
        return

    # 2. Bikin Tabel dan Index di dalam 'mbasystem'
    try:
        print(f"\n⏳ Pindah koneksi ke '{TARGET_DB}'...")
        conn = psycopg2.connect(dbname=TARGET_DB, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
        cur = conn.cursor()
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS multimodal_tracking (
            id SERIAL PRIMARY KEY,
            camera_id VARCHAR(20) NOT NULL,
            tracking_id INT NOT NULL,
            emotion VARCHAR(50),
            is_attentive BOOLEAN,
            yaw VARCHAR(20),
            pitch VARCHAR(20),
            yolo_action VARCHAR(50),
            action_conf NUMERIC(4, 2),
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            duration NUMERIC(10, 2)
        );
        """
        print("🔨 Membuat tabel 'multimodal_tracking'...")
        cur.execute(create_table_query)
        
        print("🔨 Membuat index (biar query analitik cepat)...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON multimodal_tracking(start_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_camera_id ON multimodal_tracking(camera_id);")
        
        conn.commit()
        print("✅ Tabel dan index siap digunakan!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Gagal bikin tabel: {e}")

if __name__ == "__main__":
    setup_database()