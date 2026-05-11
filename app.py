from flask import Flask, jsonify, request  # <-- Tambahkan request
import calendar
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import math
import numpy as np
import os
from scipy.stats import pearsonr, entropy

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", "~jr}J]0k1~,7e+]O"),
    "database": os.environ.get("DB_NAME", "mbasystem"),
    "host": os.environ.get("DB_HOST", "34.59.60.237"),
    "port": os.environ.get("DB_PORT", "5432")
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

YAW_MAP = {"CENTER": "FOKUS", "LEFT": "KIRI", "RIGHT": "KANAN"}
PITCH_MAP = {"CENTER": "DATAR", "DOWN": "NUNDUK", "UP": "DANGAK"}

# --- HELPER: Hitung Entropy Shannon ---
def calculate_entropy(counts_dict):
    values = list(counts_dict.values())
    if not values or sum(values) == 0:
        return 0.0
    # Konversi ke probabilitas
    probabilities = [v / sum(values) for v in values if v > 0]
    # Hitung entropy base 2
    ent = entropy(probabilities, base=2)
    return round(ent, 2)

# --- HELPER: Mapping Nama Bulan ke Angka ---
MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

@app.route('/api/analytics/monthly', methods=['GET'])
def get_monthly_analytics():
    try:
        # 1. Ambil parameter dari frontend (default ke March 2026 jika kosong)
        month_str = request.args.get('month', 'March')
        year_str = request.args.get('year', '2026')
        
        month_val = MONTH_MAP.get(month_str, 3)
        year_val = int(year_str)
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 2. Query agregasi per hari dalam satu bulan tertentu
        # Menggunakan mode() WITHIN GROUP untuk mencari data yang paling sering muncul (dominan)
        cur.execute("""
            SELECT 
                EXTRACT(DAY FROM start_time) as day_of_month,
                COUNT(*) as total_actions,
                SUM(duration) as total_duration,
                SUM(CASE WHEN is_attentive THEN duration ELSE 0 END) as attentive_duration,
                SUM(CASE WHEN yolo_action = 'Fallen / Lying' OR emotion IN ('Angry', 'Fearful') THEN 1 ELSE 0 END) as anomalies_count,
                mode() WITHIN GROUP (ORDER BY yolo_action) as dominant_action,
                mode() WITHIN GROUP (ORDER BY emotion) as dominant_emotion,
                mode() WITHIN GROUP (ORDER BY EXTRACT(HOUR FROM start_time)) as peak_hour
            FROM multimodal_tracking
            WHERE EXTRACT(YEAR FROM start_time) = %s 
              AND EXTRACT(MONTH FROM start_time) = %s
            GROUP BY EXTRACT(DAY FROM start_time)
            ORDER BY day_of_month ASC
        """, (year_val, month_val))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # 3. Format data agar sesuai dengan kebutuhan Frontend (30/31 Hari Penuh)
        # Cari tahu bulan ini ada berapa hari (misal Feb = 28, Mar = 31)
        num_days_in_month = calendar.monthrange(year_val, month_val)[1]
        
        # Jadikan dictionary untuk pencarian cepat berdasarkan tanggal
        daily_stats = {int(r['day_of_month']): r for r in rows}
        
        trendData = []
        tableData = []

        for day in range(1, num_days_in_month + 1):
            stat = daily_stats.get(day)
            
            if stat:
                # Jika ada data di hari tersebut
                tot_dur = stat['total_duration'] or 0
                att_dur = stat['attentive_duration'] or 0
                attention_avg = int((att_dur / tot_dur * 100)) if tot_dur > 0 else 0
                
                anomalies = int(stat['anomalies_count'] or 0)
                total_actions = int(stat['total_actions'] or 0)
                
                # Format jam puncak (misal 8 -> "08:00-09:00")
                ph = int(stat['peak_hour']) if stat['peak_hour'] is not None else 0
                peak_hour_str = f"{ph:02d}:00-{(ph+1)%24:02d}:00"
                
                dominant_action = stat['dominant_action'] or "None"
                dominant_emotion = stat['dominant_emotion'] or "Neutral"
            else:
                # Jika hari tersebut tidak ada aktivitas sama sekali (kosong)
                attention_avg = 0
                anomalies = 0
                total_actions = 0
                peak_hour_str = "-"
                dominant_action = "-"
                dominant_emotion = "-"
            
            # Tentukan status anomali sesuai logika frontend
            status = "critical" if anomalies >= 5 else "warning" if anomalies >= 3 else "normal"
            
            # A. Data untuk Recharts (Line Chart)
            trendData.append({
                "day": f"Day {day}",
                "actions": total_actions,
                "attention": attention_avg,
                "emotionalSpikes": anomalies # Menggunakan total anomali sebagai indikator emosi ekstrem
            })
            
            # B. Data untuk Shadcn Table
            tableData.append({
                "date": f"{year_val}-{month_val:02d}-{day:02d}",
                "peakHour": peak_hour_str,
                "action": dominant_action,
                "attention": attention_avg,
                "emotion": dominant_emotion,
                "anomalies": anomalies,
                "anomalyStatus": status
            })

        return jsonify({
            "status": "success",
            "month": month_str,
            "year": year_val,
            "data": {
                "trendData": trendData,
                "tableData": tableData
            }
        })

    except Exception as e:
        print("Error Get Monthly Analytics:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/analytics/daily', methods=['GET'])
def get_daily_analytics():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT 
                EXTRACT(HOUR FROM start_time) as hour,
                camera_id, emotion, is_attentive, yaw, pitch, yolo_action,
                duration
            FROM multimodal_tracking
            WHERE DATE(start_time) = CURRENT_DATE
        """)
        rows = cur.fetchall()

        if not rows:
            return jsonify({"status": "error", "message": "Belum ada data untuk hari ini."}), 404

        total_segments = len(rows)
        # Filter duration None, amankan jika 0
        total_duration_all = sum((r['duration'] or 0) for r in rows)

        action_durations_total = {}
        emotion_durations_total = {}
        action_stats = {} 
        camera_counts = {}
        
        # Untuk korelasi Action vs Attention per jam
        hourly_active_volume = [0] * 24
        hourly_attention_duration = [0] * 24
        hourly_total_duration = [0] * 24
        
        hourly_data = []
        for i in range(24):
            hourly_data.append({
                "hour": f"{i:02d}:00",
                "Standing": 0, "Walking": 0, "Running": 0, "Sitting": 0, "Loitering": 0,
                "Neutral": 0, "Happy": 0, "Sad": 0, "Angry": 0, "Stressed": 0,
                "total_attentive_duration": 0, "total_hour_duration": 0,
                "FOKUS": 0, "KIRI": 0, "KANAN": 0,
                "DATAR": 0, "NUNDUK": 0, "DANGAK": 0,
                "attScore": 0
            })

        for r in rows:
            act = r['yolo_action'] if r['yolo_action'] != 'None' else 'Standing'
            emo = r['emotion']
            cam = r['camera_id']
            hr = int(r['hour'])
            yaw = YAW_MAP.get(r['yaw'], "FOKUS")
            pitch = PITCH_MAP.get(r['pitch'], "DATAR")
            dur = r['duration'] if r['duration'] else 0

            # --- Basic Counts ---
            action_durations_total[act] = action_durations_total.get(act, 0) + dur
            emotion_durations_total[emo] = emotion_durations_total.get(emo, 0) + dur
            
            if act not in action_stats:
                action_stats[act] = []
            action_stats[act].append(dur)

            # --- Camera Data ---
            if cam not in camera_counts:
                camera_counts[cam] = {"camera": cam, "Standing": 0, "Walking": 0, "Running": 0, "Sitting": 0, "Loitering": 0, "total_det": 0, "att_dur": 0, "total_dur": 0}
            if act in camera_counts[cam]:
                camera_counts[cam][act] += 1
                camera_counts[cam]["total_det"] += 1
                camera_counts[cam]["total_dur"] += dur
                if r['is_attentive']:
                    camera_counts[cam]["att_dur"] += dur

            # --- Hourly Data ---
            hd = hourly_data[hr]
            hd["total_hour_duration"] += dur
            hourly_total_duration[hr] += dur
            
            if act in hd: hd[act] += dur
            if emo in hd: hd[emo] += dur
            if r['is_attentive']: 
                hd["total_attentive_duration"] += dur
                hourly_attention_duration[hr] += dur
            
            # Array khusus untuk korelasi (Active behaviors = Walking, Running)
            if act in ['Walking', 'Running']:
                hourly_active_volume[hr] += dur
            
            if yaw in hd: hd[yaw] += dur
            if pitch in hd: hd[pitch] += dur

        # --- 1. Donut Charts ---
        action_dominance = [
            {"name": k, "value": round((v/total_duration_all)*100, 1)} 
            for k, v in action_durations_total.items() if total_duration_all > 0
        ]
        emotion_dominance = [
            {"name": k, "value": round((v/total_duration_all)*100, 1)} 
            for k, v in emotion_durations_total.items() if total_duration_all > 0
        ]
        
        # --- 2. Action Durations ---
        action_durations_chart = []
        for act, durations in action_stats.items():
            if len(durations) > 0:
                action_durations_chart.append({
                    "action": act,
                    "avgDuration": math.ceil(sum(durations) / len(durations)),
                    "maxDuration": math.ceil(max(durations)),
                    "minDuration": math.ceil(min(durations))
                })

        # --- 3. Camera Data ---
        action_by_camera = []
        for cam, cdata in camera_counts.items():
            avg_att = round((cdata["att_dur"] / cdata["total_dur"] * 100)) if cdata["total_dur"] > 0 else 0
            action_by_camera.append({
                "camera": cam,
                "Standing": cdata["Standing"], "Walking": cdata["Walking"],
                "Running": cdata["Running"], "Sitting": cdata["Sitting"],
                "Loitering": cdata["Loitering"], "total_det": cdata["total_det"],
                "avg_attention": avg_att
            })
        
        # --- 4. Hourly Formatting ---
        for hd in hourly_data:
            t = hd["total_hour_duration"]
            hd["attentionAvg"] = round((hd["total_attentive_duration"] / t * 100)) if t > 0 else 0
            hd["attScore"] = hd["attentionAvg"] 
            
            if t > 0:
                hd["FOKUS"] = round((hd["FOKUS"]/t)*100, 1)
                hd["KIRI"] = round((hd["KIRI"]/t)*100, 1)
                hd["KANAN"] = round((hd["KANAN"]/t)*100, 1)
                hd["DATAR"] = round((hd["DATAR"]/t)*100, 1)
                hd["NUNDUK"] = round((hd["NUNDUK"]/t)*100, 1)
                hd["DANGAK"] = round((hd["DANGAK"]/t)*100, 1)
            
            # Normalisasi untuk bar chart (opsional)
            hd["Standing"] = min(100, hd["Standing"])
            hd["Walking"] = min(100, hd["Walking"])
            hd["Running"] = min(100, hd["Running"])
            hd["Sitting"] = min(100, hd["Sitting"])

        # --- 5. ADVANCED INSIGHTS (Baru!) ---
        
        # A. Behavioral Entropy (H)
        # Menghitung seberapa bervariasi aksi yang terjadi hari ini
        entropy_val = calculate_entropy(action_durations_total)
        max_entropy = round(math.log2(5), 2) # Max 5 class (Standing, Walking, Running, Sitting, Loitering) = 2.32
        
        # B. Action-Attention Coupling (r)
        # Korelasi Pearson antara Volume Aksi Aktif vs Skor Atensi per jam
        # Filter jam yang ada datanya
        valid_hours_idx = [i for i, t in enumerate(hourly_total_duration) if t > 0]
        if len(valid_hours_idx) > 1:
            att_scores = [(hourly_attention_duration[i] / hourly_total_duration[i]) * 100 for i in valid_hours_idx]
            act_vols = [hourly_active_volume[i] for i in valid_hours_idx]
            
            # Cek standar deviasi biar Pearsonr gak error kalau datanya konstan/statis
            if np.std(att_scores) == 0 or np.std(act_vols) == 0:
                coupling_r = 0.0
            else:
                coupling_r, _ = pearsonr(act_vols, att_scores)
        else:
            coupling_r = 0.0
            
        coupling_r = round(coupling_r, 2)
        
        # C. Attention Decay
        # Mengukur penurunan atensi dari siang (12:00) ke sore (18:00)
        afternoon_hours = [i for i in range(12, 19) if hourly_total_duration[i] > 0]
        if len(afternoon_hours) >= 2:
            scores = [(hourly_attention_duration[i] / hourly_total_duration[i]) * 100 for i in afternoon_hours]
            decay_rate = round((scores[-1] - scores[0]) / len(afternoon_hours), 1)
        else:
            decay_rate = 0.0

        # --- 6. KPIs ---
        dom_action = max(action_durations_total, key=action_durations_total.get) if action_durations_total else "N/A"
        dom_emotion = max(emotion_durations_total, key=emotion_durations_total.get) if emotion_durations_total else "N/A"
        total_attentive_duration = sum((r['duration'] or 0) for r in rows if r['is_attentive'])
        avg_att_all = round((total_attentive_duration / total_duration_all * 100), 1) if total_duration_all > 0 else 0

        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "kpis": {
                "total_detections": total_segments, 
                "dominant_action": dom_action,
                "dominant_emotion": dom_emotion,
                "overall_attention": avg_att_all # <--- Fix 0% disini!
            },
            "insights": {
                "entropy": entropy_val,
                "max_entropy": max_entropy,
                "coupling_r": coupling_r,
                "decay_rate": decay_rate
            },
            "action_dominance": action_dominance,
            "emotion_dominance": emotion_dominance,
            "action_durations": action_durations_chart,
            "action_by_camera": action_by_camera,
            "hourly_data": hourly_data
        })

    except Exception as e:
        print("Error Backend Flask:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    
    


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)