import psycopg2
from psycopg2.extras import execute_values  # <-- 1. PERUBAHAN IMPORT: Tambah baris ini
import os
import random
import calendar
from datetime import datetime, timedelta

# ─── KONFIGURASI DATABASE ───
DB_CONFIG = {
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", "DezYnNbD\~2\S:|5"),
    "database": os.environ.get("DB_NAME", "mbabatch2"),
    "host": os.environ.get("DB_HOST", "136.119.162.109"),
    "port": os.environ.get("DB_PORT", "5432")
}



# ─── DATA KATEGORI ───
CAMERAS = ["cam-01", "cam-02", "cam-03", "cam-04", "cam-05", "cam-06"]
ACTIONS = ["Standing", "Walking", "Sitting", "Fallen / Lying", "Drinking"]
EMOTIONS = ["Neutral", "Happy", "Sad", "Angry", "Fearful"]
YAWS = ["CENTER", "LEFT", "RIGHT"]
PITCHES = ["CENTER", "DOWN", "UP"]

def get_daily_pattern(target_date):
    """Menentukan pola traffic berdasarkan hari (Weekday, Weekend, atau Event)"""
    day = target_date.day
    weekday = target_date.weekday() # 0=Senin, 6=Minggu
    
    # Anomali: Simulasi hari "Event/Insiden" di tanggal 15 Mei
    if day == 15:
        return {
            "num_records": random.randint(3000, 4000),
            "hour_weights": [2,2,2,2,2,5,10,20,30,40,50,40,30,20,15,10,10,8,8,5,5,3,2,2],
            "action_weights": [30, 40, 20, 5, 5], 
            "emotion_weights": [40, 30, 10, 10, 10]
        }
    # Weekend (Sabtu, Minggu)
    elif weekday >= 5:
        return {
            "num_records": random.randint(500, 1000),
            "hour_weights": [1,1,2,2,2,3,5,8,12,15,18,20,20,18,15,12,8,5,5,3,2,2,1,1],
            "action_weights": [40, 45, 10, 1, 4], 
            "emotion_weights": [50, 35, 5, 5, 5]  
        }
    # Weekday (Senin - Jumat)
    else:
        return {
            "num_records": random.randint(1800, 2500),
            "hour_weights": [1,1,1,1,1,2,5,15,20,15,15,20,25,20,15,15,15,10,8,5,3,2,1,1], 
            "action_weights": [25, 30, 40, 1, 4], 
            "emotion_weights": [70, 15, 5, 5, 5]  
        }

def generate_dummy_data_for_date(target_date):
    """Generate data spesifik untuk satu hari sesuai pola"""
    data = []
    pattern = get_daily_pattern(target_date)
    num_records = pattern["num_records"]
    
    for _ in range(num_records):
        cam = random.choice(CAMERAS)
        tid = random.randint(1, 150)
        
        # 1. Tentukan Waktu Start
        hour = random.choices(population=range(24), weights=pattern["hour_weights"], k=1)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        start_time = datetime(target_date.year, target_date.month, target_date.day, hour, minute, second)
        
        # 2. Tentukan Aksi & Durasi
        act = random.choices(ACTIONS, weights=pattern["action_weights"], k=1)[0]
        
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
        
        # 3. Emosi Logis yang dipengaruhi aksi
        if act == "Fallen / Lying":
            emo = random.choices(EMOTIONS, weights=[20, 10, 35, 5, 30], k=1)[0]
        else:
            emo = random.choices(EMOTIONS, weights=pattern["emotion_weights"], k=1)[0]
            
        yaw = random.choices(YAWS, weights=[75, 12.5, 12.5], k=1)[0]
        pitch = random.choices(PITCHES, weights=[75, 15, 10], k=1)[0]
        
        # 4. Atensi
        is_attentive = True if yaw == "CENTER" and pitch == "CENTER" else False
        conf = round(random.uniform(0.70, 0.99), 2)
        
        data.append((cam, tid, emo, is_attentive, yaw, pitch, act, conf, start_time, end_time, dur))
        
    return data

def inject_month_data(year=2026, month=6):
    """Mengeksekusi generasi data untuk satu bulan penuh dan menginjeksinya ke DB"""
    print(f"🚀 Memulai injeksi data untuk bulan {month}-{year}...")
    
    # <-- 2. PERUBAHAN QUERY: Hanya gunakan %s tunggal di VALUES
    query = """
        INSERT INTO multimodal_tracking 
        (camera_id, tracking_id, emotion, is_attentive, yaw, pitch, yolo_action, action_conf, start_time, end_time, duration)
        VALUES %s
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("🔌 Database connected.")
        print(f"🧹 Membersihkan data lama untuk bulan {month} tahun {year}...")
        
        delete_query = """
            DELETE FROM multimodal_tracking 
            WHERE EXTRACT(MONTH FROM start_time) = %s 
            AND EXTRACT(YEAR FROM start_time) = %s
        """
        cur.execute(delete_query, (month, year))
        conn.commit()
        
        num_days = calendar.monthrange(year, month)[1]
        total_records_injected = 0
        
        for day in range(1, num_days + 1):
            target_date = datetime(year, month, day).date()
            
            # Generate record untuk hari tersebut
            daily_records = generate_dummy_data_for_date(target_date)
            
            # <-- 3. PERUBAHAN EKSEKUSI: Panggil execute_values untuk Multi-row Insert
            execute_values(cur, query, daily_records)
            conn.commit()
            
            total_records_injected += len(daily_records)
            print(f"✅ Tgl {day:02d}-{month:02d}-{year}: Injeksi {len(daily_records)} records selesai.")
            
        print(f"\n🎉 SUCCESS FULL MONTH! Total {total_records_injected} records injected untuk Mei 2026.")
        
    except Exception as e:
        print("❌ Error:", e)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    inject_month_data(year=2026, month=6)