import psycopg2
from psycopg2.extras import execute_values
import os
import random
from datetime import datetime, timedelta, date

# ─── KONFIGURASI DATABASE ───



# ─── DATA KATEGORI ───
CAMERAS = ["cam-01", "cam-02", "cam-03", "cam-04", "cam-05", "cam-06"]
ACTIONS = ["Standing", "Walking", "Sitting", "Fallen / Lying", "Drinking"]
EMOTIONS = ["Neutral", "Happy", "Sad", "Angry", "Fearful"]
YAWS = ["CENTER", "LEFT", "RIGHT"]
PITCHES = ["CENTER", "DOWN", "UP"]

def generate_dummy_data(target_date, num_records=2000):
    data = []
    
    for _ in range(num_records):
        cam = random.choice(CAMERAS)
        tid = random.randint(1, 150)
        
        # 1. Waktu Random (Distribusi Jam Sibuk)
        hour = random.choices(
            population=range(24),
            weights=[1,1,1,1,1,2,5,15,20,15,15,20,25,20,15,15,15,10,8,5,3,2,1,1],
            k=1
        )[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        start_time = datetime(target_date.year, target_date.month, target_date.day, hour, minute, second)
        
        # 2. Aksi & Durasi Logis
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
        
        # 3. Emosi Logis
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
    start_date = date(2026, 5, 1)
    end_date = date(2026, 6, 30)
    
    all_records = []
    curr_date = start_date
    
    print("⏳ Generating data in memory first...")
    while curr_date <= end_date:
        all_records.extend(generate_dummy_data(curr_date, 2000))
        curr_date += timedelta(days=1)
        
    # Perhatikan syntax %s tanpa kurung untuk execute_values
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
        
        # Bersihkan dulu rentang Mei - Juni agar aman kalau dirun ulang
        print("🧹 Cleaning old data for May and June 2026...")
        cur.execute("DELETE FROM multimodal_tracking WHERE start_time >= '2026-05-01' AND start_time < '2026-07-01'")
        
        print(f"💉 Injecting {len(all_records)} total records efficiently...")
        # execute_values dengan page_size mengelompokkan data per 5000 baris per eksekusi
        execute_values(cur, query, all_records, page_size=5000)
        conn.commit()
        print(f"✅ SUCCESS! {len(all_records)} records injected. Go check your dashboard!")
        
    except Exception as e:
        print("❌ Error:", e)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    inject_to_db()