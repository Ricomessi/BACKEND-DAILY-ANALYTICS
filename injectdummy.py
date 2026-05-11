import psycopg2
import os
import random
from datetime import datetime, timedelta

# ─── KONFIGURASI DATABASE ───

DB_CONFIG = {
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", "~jr}J]0k1~,7e+]O"),
    "database": os.environ.get("DB_NAME", "mbasystem"),
    "host": os.environ.get("DB_HOST", "34.59.60.237"),
    "port": os.environ.get("DB_PORT", "5432")
}

# ─── DATA KATEGORI (UPDATED) ───
CAMERAS = ["cam-01", "cam-02", "cam-03", "cam-04", "cam-05", "cam-06"]
# Sudah disesuaikan dengan Master Class hasil peleburan kelas YOLO lo
ACTIONS = ["Standing", "Walking", "Sitting", "Fallen / Lying", "Drinking"]
# Sudah disesuaikan dengan output asli sensor face-api.js
EMOTIONS = ["Neutral", "Happy", "Sad", "Angry", "Fearful"]
YAWS = ["CENTER", "LEFT", "RIGHT"]
PITCHES = ["CENTER", "DOWN", "UP"]

def generate_dummy_data(num_records=2000):
    data = []
    today = datetime.now().date()
    
    for _ in range(num_records):
        cam = random.choice(CAMERAS)
        tid = random.randint(1, 150) # Mengurangi jumlah ID agar korelasi per orang lebih kuat
        
        # 1. Waktu Random (Distribusi Jam Sibuk)
        hour = random.choices(
            population=range(24),
            weights=[1,1,1,1,1,2,5,15,20,15,15,20,25,20,15,15,15,10,8,5,3,2,1,1],
            k=1
        )[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        start_time = datetime(today.year, today.month, today.day, hour, minute, second)
        
        # 2. Aksi & Durasi Logis (Sesuai Kategori Baru)
        # Standing & Walking paling sering, Fallen & Drinking jarang (anomali)
        act = random.choices(ACTIONS, weights=[40, 35, 15, 5, 5], k=1)[0]
        
        if act == "Fallen / Lying": 
            dur = random.uniform(5, 60) # Kalau jatuh biasanya agak lama di lantai
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
        
        # 3. Emosi Logis ( face-api.js )
        # Jika Fallen, naikkan probabilitas Sad atau Fearful
        if act == "Fallen / Lying":
            emo = random.choices(EMOTIONS, weights=[20, 10, 35, 5, 30], k=1)[0]
        else:
            emo = random.choices(EMOTIONS, weights=[60, 20, 10, 5, 5], k=1)[0]
            
        yaw = random.choices(YAWS, weights=[75, 12.5, 12.5], k=1)[0]
        pitch = random.choices(PITCHES, weights=[75, 15, 10], k=1)[0]
        
        # 4. Atensi
        is_attentive = True if yaw == "CENTER" and pitch == "CENTER" else False
        conf = round(random.uniform(0.70, 0.99), 2)
        
        data.append((cam, tid, emo, is_attentive, yaw, pitch, act, conf, start_time, end_time, dur))
        
    return data

def inject_to_db():
    print(f"⏳ Generating 2000 records for {datetime.now().date()}...")
    records = generate_dummy_data(2000)
    
    query = """
        INSERT INTO multimodal_tracking 
        (camera_id, tracking_id, emotion, is_attentive, yaw, pitch, yolo_action, action_conf, start_time, end_time, duration)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("🔌 Database connected. Cleaning old data for today...")
        
        # Opsional: Hapus data hari ini dulu biar gak dobel pas lo running berkali-kali
        cur.execute("DELETE FROM multimodal_tracking WHERE DATE(start_time) = CURRENT_DATE")
        
        print("💉 Injecting new records...")
        cur.executemany(query, records)
        conn.commit()
        print(f"✅ SUCCESS! {len(records)} records injected. Go check your dashboard!")
        
    except Exception as e:
        print("❌ Error:", e)
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    inject_to_db()