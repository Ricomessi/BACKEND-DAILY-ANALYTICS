from flask import Flask, jsonify, request  
import calendar
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import math
import numpy as np
import os
from scipy.stats import pearsonr, entropy
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
CORS(app)

def get_db_connection():
    # Ambil credentials dasar
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASS", "DezYnNbD\~2\S:|5")
    db_name = os.environ.get("DB_NAME", "mbabatch2")
    
    # Cek apakah ada environment variable INSTANCE_CONNECTION_NAME
    # (Ini akan dipakai saat jalan di Cloud Run)
    instance_connection_name = os.environ.get("INSTANCE_CONNECTION_NAME")
    
    if instance_connection_name:
        # MODE CLOUD RUN: Koneksi via Unix Socket
        return psycopg2.connect(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=f"/cloudsql/{instance_connection_name}"
            # Port tidak perlu didefinisikan jika menggunakan Unix Socket
        )
    else:
        # MODE LOKAL: Koneksi via TCP (IP Address biasa)
        return psycopg2.connect(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=os.environ.get("DB_HOST", "136.119.162.109"),
            port=os.environ.get("DB_PORT", "5432")
        )

# def get_db_connection():
#     return psycopg2.connect(**DB_CONFIG)

YAW_MAP = {"CENTER": "FOKUS", "LEFT": "KIRI", "RIGHT": "KANAN"}
PITCH_MAP = {"CENTER": "DATAR", "DOWN": "NUNDUK", "UP": "DANGAK"}

# --- HELPER: Hitung Entropy Shannon ---
def calculate_entropy(counts_dict):
    values = list(counts_dict.values())
    if not values or sum(values) == 0:
        return 0.0
    probabilities = [v / sum(values) for v in values if v > 0]
    ent = entropy(probabilities, base=2)
    return round(ent, 2)

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

@app.route('/api/analytics/monthly', methods=['GET'])
def get_monthly_analytics():
    try:
        month_str = request.args.get('month', 'March')
        year_str = request.args.get('year', '2026')
        month_val = MONTH_MAP.get(month_str, 3)
        year_val = int(year_str)
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

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

        num_days_in_month = calendar.monthrange(year_val, month_val)[1]
        daily_stats = {int(r['day_of_month']): r for r in rows}
        
        trendData = []
        tableData = []

        for day in range(1, num_days_in_month + 1):
            stat = daily_stats.get(day)
            
            if stat:
                tot_dur = stat['total_duration'] or 0
                att_dur = stat['attentive_duration'] or 0
                attention_avg = int((att_dur / tot_dur * 100)) if tot_dur > 0 else 0
                anomalies = int(stat['anomalies_count'] or 0)
                total_actions = int(stat['total_actions'] or 0)
                ph = int(stat['peak_hour']) if stat['peak_hour'] is not None else 0
                peak_hour_str = f"{ph:02d}:00-{(ph+1)%24:02d}:00"
                dominant_action = stat['dominant_action'] or "None"
                dominant_emotion = stat['dominant_emotion'] or "Neutral"
            else:
                attention_avg = 0
                anomalies = 0
                total_actions = 0
                peak_hour_str = "-"
                dominant_action = "-"
                dominant_emotion = "-"
            
            status = "critical" if anomalies >= 5 else "warning" if anomalies >= 3 else "normal"
            
            trendData.append({
                "day": f"Day {day}",
                "actions": total_actions,
                "attention": attention_avg,
                "emotionalSpikes": anomalies
            })
            
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
    
@app.route('/api/rules', methods=['GET', 'POST', 'DELETE'])
def manage_rules():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if request.method == 'GET':
        cur.execute("SELECT * FROM anomaly_rules ORDER BY id ASC")
        rules = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "data": rules})
        
    elif request.method == 'POST':
        data = request.json
        cur.execute("""
            INSERT INTO anomaly_rules (field, operator, value, min_duration, severity, rule_type, message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data['field'], data['operator'], data['value'], data.get('min_duration', 0), 
              data['severity'], data['rule_type'], data['message']))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Rule ditambahkan!"})
        
    elif request.method == 'DELETE':
        rule_id = request.args.get('id')
        if rule_id:
            cur.execute("DELETE FROM anomaly_rules WHERE id = %s", (rule_id,))
            conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Rule dihapus!"})
        
@app.route('/api/analytics/daily', methods=['GET'])
def get_daily_analytics():
    try:
        target_date = request.args.get('date')
        
        # 2. Fallback: Jika parameter kosong, gunakan tanggal hari ini di zona waktu WIB (UTC+7)
        if not target_date:
            wib_timezone = timezone(timedelta(hours=7))
            target_date = datetime.now(wib_timezone).strftime('%Y-%m-%d')
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
           SELECT 
                EXTRACT(HOUR FROM start_time) as hour,
                EXTRACT(MINUTE FROM start_time) as minute,  -- <--- TAMBAHKAN BARIS INI
                camera_id, emotion, is_attentive, yaw, pitch, yolo_action,
                CAST(duration AS FLOAT) as duration
            FROM multimodal_tracking
            WHERE DATE(start_time) = %s
        """, (target_date,))
        rows = cur.fetchall()

        if not rows:
            return jsonify({"status": "error", "message": "Belum ada data untuk hari ini."}), 404

        total_segments = len(rows)
        total_duration_all = sum((r['duration'] or 0) for r in rows)

        action_durations_total = {}
        emotion_durations_total = {}
        action_stats = {} 
        camera_counts = {}
        
        hourly_active_volume = [0] * 24
        hourly_attention_duration = [0] * 24
        hourly_total_duration = [0] * 24
        
        hourly_data = []
        for i in range(24):
            hourly_data.append({
                "hour": f"{i:02d}:00",
                "Standing": 0, "Walking": 0, "Running": 0, "Sitting": 0, "Loitering": 0, "Fallen / Lying": 0, "Drinking": 0,
                "Neutral": 0, "Happy": 0, "Sad": 0, "Angry": 0, "Fearful": 0,
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
            
            hd["Standing"] = min(100, hd["Standing"])
            hd["Walking"] = min(100, hd["Walking"])
            hd["Running"] = min(100, hd["Running"])
            hd["Sitting"] = min(100, hd["Sitting"])

        # --- 5. ADVANCED INSIGHTS ---
        entropy_val = calculate_entropy(action_durations_total)
        max_entropy = round(math.log2(5), 2)
        
        valid_hours_idx = [i for i, t in enumerate(hourly_total_duration) if t > 0]
        if len(valid_hours_idx) > 1:
            att_scores = [(hourly_attention_duration[i] / hourly_total_duration[i]) * 100 for i in valid_hours_idx]
            act_vols = [hourly_active_volume[i] for i in valid_hours_idx]
            if np.std(att_scores) == 0 or np.std(act_vols) == 0:
                coupling_r = 0.0
            else:
                coupling_r, _ = pearsonr(act_vols, att_scores)
        else:
            coupling_r = 0.0
            
        coupling_r = round(coupling_r, 2)
        
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

        # --- 7. Gaze Segment Distribution ---
        buckets = {"0-5s": 0, "6-15s": 0, "16-30s": 0, "31-60s": 0, ">60s": 0}
        for r in rows:
            if r['is_attentive']:
                d = r['duration'] or 0
                if d <= 5: buckets["0-5s"] += 1
                elif d <= 15: buckets["6-15s"] += 1
                elif d <= 30: buckets["16-30s"] += 1
                elif d <= 60: buckets["31-60s"] += 1
                else: buckets[">60s"] += 1
        gaze_segments = [{"range": k, "count": v} for k, v in buckets.items()]
        
# --- 8. Cross-Modal Features (UNTUK FRONTEND) ---
        actions_list = ["Standing", "Walking", "Sitting", "Fallen / Lying", "Drinking"]
        emotions_list = ["Neutral", "Happy", "Sad", "Angry", "Fearful"]
        
        transition_matrix = [[0 for _ in range(5)] for _ in range(5)]
        emotion_action_matrix = [[0 for _ in range(5)] for _ in range(5)]
        scatter_data = []
        anomaly_timeline = []
        
        camera_history = {}

        # =======================================================
        # ⚙️ AMBIL RULE ENGINE DARI DATABASE (TARUH DI LUAR LOOP!)
        # =======================================================
        cur.execute("SELECT * FROM anomaly_rules WHERE is_active = TRUE")
        db_rules = cur.fetchall()
        
        for r in rows:
            # -- Transition Matrix --
            cam = r['camera_id']
            raw_act = r['yolo_action']
            act = raw_act if raw_act in actions_list else 'Standing'
            emo = r['emotion'] if r['emotion'] in emotions_list else 'Neutral'
            
            if cam in camera_history:
                prev_act = camera_history[cam]
                if prev_act in actions_list and act in actions_list:
                    prev_idx = actions_list.index(prev_act)
                    curr_idx = actions_list.index(act)
                    transition_matrix[prev_idx][curr_idx] += 1
            camera_history[cam] = act

            # -- Emotion-Action Matrix --
            if emo in emotions_list and act in actions_list:
                e_idx = emotions_list.index(emo)
                a_idx = actions_list.index(act)
                emotion_action_matrix[e_idx][a_idx] += 1
                
            # -- Scatter Data (Attention vs Emotion) --
            if len(scatter_data) < 200:
                 att_val = 100 if r['is_attentive'] else (0 if not r['duration'] else min((r['duration']*10), 80))
                 e_idx = emotions_list.index(emo) if emo in emotions_list else 0
                 scatter_data.append({
                     "attention": att_val,
                     "emotion": emo,
                     "emotionIndex": e_idx,
                     "size": (r['duration'] or 1) * 20 
                 })
                 
            # =======================================================
            # ⚙️ EKSEKUSI RULE ENGINE KE DATA (DI DALAM LOOP)
            # =======================================================
            for rule in db_rules:
                is_anomaly = False
                field_value = str(r.get(rule['field'], "")).strip() 
                
                # 1. Cek Operator Dasar
                if rule['operator'] == '==':
                    if field_value.lower() == str(rule['value']).strip().lower():
                        is_anomaly = True
                elif rule['operator'] == 'in':
                    valid_values = [v.strip().lower() for v in rule['value'].split(',')]
                    if field_value.lower() in valid_values:
                        is_anomaly = True
                    
                # 2. Cek Syarat Durasi
                if is_anomaly and rule['min_duration'] > 0:
                    dur = r['duration'] or 0
                    if dur < rule['min_duration']:
                        is_anomaly = False
                
                # 3. Masukkan ke Timeline
                if is_anomaly:
                    jam = int(r['hour'])
                    menit = int(r.get('minute', 0))
                    
                    anomaly_timeline.append({
                        "hour": f"{jam:02d}:{menit:02d}",
                        "severity": rule['severity'],
                        "type": rule['rule_type'],
                        "label": rule['message'].format(
                            cam=r['camera_id'], 
                            emo=r['emotion'], 
                            act=r['yolo_action'], 
                            dur=r.get('duration', 0)
                        )
                    })

        # Urutkan timeline berdasarkan jam & menit
        anomaly_timeline = sorted(anomaly_timeline, key=lambda x: x['hour'], reverse=True)[:15]
        # Normalisasi Emotion-Action Matrix untuk Heatmap (0.0 - 1.0)
        for i in range(len(emotion_action_matrix)):
            row_sum = sum(emotion_action_matrix[i])
            if row_sum > 0:
                emotion_action_matrix[i] = [round(val/row_sum, 2) for val in emotion_action_matrix[i]]


        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "kpis": {
                "total_detections": total_segments, 
                "dominant_action": dom_action,
                "dominant_emotion": dom_emotion,
                "overall_attention": avg_att_all
            },
            "insights": {
                "entropy": entropy_val,
                "max_entropy": max_entropy,
                "coupling_r": coupling_r,
                "decay_rate": decay_rate
            },
            "features": {
                "transition_matrix": transition_matrix,
                "emotion_action_matrix": emotion_action_matrix,
                "scatter_data": scatter_data,
                "segment_buckets": gaze_segments,
                "anomaly_timeline": anomaly_timeline
            },
            "gaze_segments": gaze_segments, 
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