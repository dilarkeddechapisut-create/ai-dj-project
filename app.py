import streamlit as st
import pandas as pd
import joblib
import random
import os

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")
st.markdown("พิมพ์บอกความรู้สึกของคุณ แล้วให้ AI DJ จัดเพลงให้เลย!")

# 2. โหลดโมเดลด้วย Cache เพื่อให้ทำงานเร็วขึ้นบน Cloud
@st.cache_resource
def load_models():
    try:
        km = joblib.load('kmeans_model.pkl')
        sc = joblib.load('scaler.pkl')
        df = pd.read_csv('spotify_clustered.csv')
        return km, sc, df
    except Exception as e:
        st.error(f"ไม่พบไฟล์โมเดล กรุณาอัปโหลดไฟล์ .pkl และ .csv ขึ้น GitHub ด้วย: {e}")
        return None, None, None

kmeans, scaler, df_songs = load_models()

# 3. ระบบวิเคราะห์อารมณ์เป็นตัวเลข (NLP Rule-based)
def analyze_mood_to_features(text):
    text = text.lower()
    energy, valence, tempo = 0.5, 0.5, 100.0 
    
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ร้องไห้", "เหนื่อย", "ดิ่ง"]):
        energy, valence, tempo = 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น", "ปาร์ตี้", "ตื่นเต้น", "สดใส"]):
        energy, valence, tempo = 0.8, 0.8, 130.0
    elif any(word in text for word in ["ชิล", "สบาย", "ทำงาน", "อ่านหนังสือ", "กาแฟ", "พักผ่อน"]):
        energy, valence, tempo = 0.4, 0.6, 90.0
    elif any(word in text for word in ["โกรธ", "โมโห", "เดือด", "ร็อค"]):
        energy, valence, tempo = 0.9, 0.3, 140.0
        
    return energy, valence, tempo

# 4. ระบบจำลองข้อความ DJ (แทน Ollama)
def generate_dj_message(mood):
    templates = [
        f"โย่ว! จากที่คุณบอกว่า '{mood}' DJ จัด Playlist ชุดนี้มาให้ รับรองว่าโดนใจและเข้ากับฟีลตอนนี้สุดๆ ไปฟังกันเลย!",
        f"เข้าใจความรู้สึกเลยครับที่บอกว่า '{mood}' ลองปล่อยใจจอยๆ แล้วฟัง 5 เพลงที่ผมคัดมาให้นี้ดูนะครับ เป็นกำลังใจให้!",
        f"ได้ยินว่า '{mood}' จัดไปครับ! นี่คือลิสต์เพลงที่ระบบวิเคราะห์มาแล้วว่าตรงกับ Vibe ของคุณในเวลานี้ Enjoy!"
    ]
    return random.choice(templates)

# 5. หน้า UI หลัก
mood_text = st.text_area("วันนี้คุณรู้สึกอย่างไร?", placeholder="เช่น วันนี้ฝนตก เหงาจังเลย อยากได้เพลงฮีลใจ")

if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", use_container_width=True):
    if not mood_text:
        st.warning("กรุณาพิมพ์ความรู้สึกของคุณก่อนครับ")
    elif kmeans is not None:
        with st.spinner("AI กำลังตีความอารมณ์และจัดเพลง..."):
            # ก. แปลงข้อความเป็นฟีเจอร์
            t_energy, t_valence, t_tempo = analyze_mood_to_features(mood_text)
            
            # ข. นำไป Predict เข้า K-Means
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            scaled_input = scaler.transform(user_features)
            predicted_cluster = kmeans.predict(scaled_input)[0]
            
            # ค. สุ่มเพลงจาก Cluster
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(5, len(cluster_songs)))
            
            song_list_str = "\n".join([
                f"- {row['track_name']} (ศิลปิน: {row['artists']})" 
                for _, row in sampled_songs.iterrows()
            ])
            
            # ง. แสดงผลลัพธ์
            st.success("จัดเพลงเสร็จเรียบร้อย!")
            st.markdown("### 💬 ข้อความจาก DJ AI")
            st.info(generate_dj_message(mood_text))
            
            st.markdown(f"### 🎼 รายชื่อเพลง (กลุ่มดนตรีที่ {predicted_cluster})")
            st.text(song_list_str)