import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import execute_values
import os
import random
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

# Muat variabel dari file .env (Pastikan file .env sudah ada!)
load_dotenv()

B_NAME", "fixedcloud")

# Konfigurasi dasar untuk koneksi awal (buat bikin database)
BASE_CONFIG = {
    "user": DB_USER,
    "password": DB_PASS,
    "host": DB_HOST,
    "port": DB_PORT,
    "database": "postgres" # Konek ke database default dulu
}

# Konfigurasi utama untuk aplikasi
DB_CONFIG = BASE_CONFIG.copy()
DB_CONFIG["database"] = DB_NAME

# ─── DATA KATEGORI ───
CAMERAS = ["cam-01", "cam-02", "cam-03", "cam-04", "cam-05", "cam-06"]
ACTIONS = ["Standing", "Walking", "Sitting", "Fallen / Lying", "Drinking"]
EMOTIONS = ["Neutral", "Happy", "Sad", "Angry", "Fearful"]
YAWS = ["CENTER", "LEFT", "RIGHT"]
PITCHES = ["CENTER", "DOWN", "UP"]

def setup_database_and_tables():
    print("⚙️ Memulai inisialisasi database...")
    
    # 1. BUAT DATABASE
    conn = None
    try:
        conn = psycopg2.connect(**BASE_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) # Wajib untuk CREATE DATABASE
        cur = conn.cursor()
        
        # Cek apakah database sudah ada
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
        exists = cur.fetchone()
        
        if not exists:
            print(f"🔨 Membuat database '{DB_NAME}'...")
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"✅ Database '{DB_NAME}' berhasil dibuat.")
        else:
            print(f"✅ Database '{DB_NAME}' sudah ada.")
            
    except Exception as e:
        print("❌ Gagal mengecek/membuat database:", e)
        return False
    finally:
        if conn: conn.close()

    # 2. BUAT TABEL
    try:
        print(f"🔌 Menghubungkan ke database '{DB_NAME}' untuk membuat tabel...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Tabel: multimodal_tracking
        print("🔨 Mengecek/Membuat tabel 'multimodal_tracking'...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS multimodal_tracking (
                id SERIAL PRIMARY KEY,
                camera_id VARCHAR(50),
                tracking_id INT,
                emotion VARCHAR(50),
                is_attentive BOOLEAN,
                yaw VARCHAR(20),
                pitch VARCHAR(20),
                yolo_action VARCHAR(50),
                action_conf REAL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration REAL
            );
        """)

        # Tabel: anomaly_rules
        print("🔨 Mengecek/Membuat tabel 'anomaly_rules'...")
        cur.execute("""
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
        """)

        conn.commit()
        print("✅ Semua tabel siap digunakan!\n")
        return True
        
    except Exception as e:
        print("❌ Gagal membuat tabel:", e)
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def generate_dummy_data(target_date, num_records=2000):
    data = []
    
    for _ in range(num_records):
        cam = random.choice(CAMERAS)
        tid = random.randint(1, 150)
        
        hour = random.choices(
            population=range(24),
            weights=[1,1,1,1,1,2,5,15,20,15,15,20,25,20,15,15,15,10,8,5,3,2,1,1],
            k=1
        )[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        start_time = datetime(target_date.year, target_date.month, target_date.day, hour, minute, second)
        
        act = random.choices(ACTIONS, weights=[40, 35, 15, 5, 5], k=1)[0]
        
        if act == "Fallen / Lying": 
            dur = random.uniform(5, 60)
        elif act == "Walking": 
            dur = random.uniform(3, 30)
        elif act == "Sitting": 
            dur = random.uniform(30, 900)
        elif act == "Drinking": 
            dur = random.uniform(5, 20)
        else: # Standing
            dur = random.uniform(5, 300)
        
        dur = round(dur, 1)
        end_time = start_time + timedelta(seconds=dur)
        
        if act == "Fallen / Lying":
            emo = random.choices(EMOTIONS, weights=[20, 10, 35, 5, 30], k=1)[0]
        else:
            emo = random.choices(EMOTIONS, weights=[60, 20, 10, 5, 5], k=1)[0]
            
        yaw = random.choices(YAWS, weights=[75, 12.5, 12.5], k=1)[0]
        pitch = random.choices(PITCHES, weights=[75, 15, 10], k=1)[0]
        
        is_attentive = True if yaw == "CENTER" and pitch == "CENTER" else False
        conf = round(random.uniform(0.70, 0.99), 2)
        
        data.append((cam, tid, emo, is_attentive, yaw, pitch, act, conf, start_time, end_time, dur))
        
    return data

def inject_to_db():
    start_date = date(2026, 5, 1)
    end_date = date(2026, 6, 30)
    
    all_records = []
    curr_date = start_date
    
    print("⏳ Generating data in memory first (May & June 2026)...")
    while curr_date <= end_date:
        all_records.extend(generate_dummy_data(curr_date, 2000))
        curr_date += timedelta(days=1)
        
    query = """
        INSERT INTO multimodal_tracking 
        (camera_id, tracking_id, emotion, is_attentive, yaw, pitch, yolo_action, action_conf, start_time, end_time, duration)
        VALUES %s
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print(f"🔌 Connected to '{DB_NAME}' for injection.")
        
        print("🧹 Cleaning old data for May and June 2026...")
        cur.execute("DELETE FROM multimodal_tracking WHERE start_time >= '2026-05-01' AND start_time < '2026-07-01'")
        
        print(f"💉 Injecting {len(all_records)} total records efficiently...")
        execute_values(cur, query, all_records, page_size=5000)
        conn.commit()
        print(f"✅ SUCCESS! {len(all_records)} records injected. Go check your dashboard!")
        
    except Exception as e:
        print("❌ Error during injection:", e)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    # Jalankan setup database dan tabel dulu
    is_setup_success = setup_database_and_tables()
    
    # Kalau setup berhasil (atau DB/Tabel sudah ada), baru injeksi datanya
    if is_setup_success:
        inject_to_db()