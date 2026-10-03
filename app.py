import streamlit as st
import pandas as pd
import joblib
import os
import csv
from datetime import datetime
import plotly.graph_objects as go
import google.generativeai as genai

st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")
st.markdown("พิมพ์บอกความรู้สึกของคุณ แล้วให้ AI DJ จัดเพลงให้เลย!")

# 1. ตั้งค่า Google Gemini API
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-3.6-flash')
except Exception as e:
    st.error("🚨 ไม่พบ API Key! กรุณาตั้งค่า GOOGLE_API_KEY ใน Streamlit Secrets")
    st.stop()

# 2. โหลดโมเดล
@st.cache_resource
def load_models():
    km = joblib.load('kmeans_model.pkl')
    sc = joblib.load('scaler.pkl')
    df = pd.read_csv('spotify_clustered.csv')
    return km, sc, df

try:
    kmeans, scaler, df_songs = load_models()
except Exception as e:
    st.error("ไม่พบไฟล์โมเดล .pkl หรือ .csv กรุณาอัปโหลดขึ้น GitHub ให้ครบ")
    st.stop()

# 3. ฟังก์ชันวิเคราะห์อารมณ์
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

# 4. ฟังก์ชันบันทึก Feedback ลง CSV
def save_feedback(mood, cluster, feedback_type):
    file_exists = os.path.isfile('feedback_log.csv')
    with open('feedback_log.csv', mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'User_Mood', 'Predicted_Cluster', 'Feedback']) # สร้างหัวตาราง
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, mood, cluster, feedback_type])

# ---------------------------------------------------------
# ระบบ Session State เพื่อจำผลลัพธ์ไม่ให้หายไปตอนกดปุ่ม Feedback
if 'playlist_data' not in st.session_state:
    st.session_state.playlist_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False
# ---------------------------------------------------------

mood_text = st.text_area("วันนี้คุณรู้สึกอย่างไร?", placeholder="เช่น วันนี้ฝนตก เหงาจังเลย อยากได้เพลงฮีลใจ")

# เมื่อกดปุ่ม จัด Playlist
if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", use_container_width=True):
    if not mood_text:
        st.warning("กรุณาพิมพ์ความรู้สึกของคุณก่อนครับ")
    else:
        with st.spinner("DJ (Gemini) กำลังวิเคราะห์อารมณ์และจัดเพลง..."):
            t_energy, t_valence, t_tempo = analyze_mood_to_features(mood_text)
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            scaled_input = scaler.transform(user_features)
            predicted_cluster = kmeans.predict(scaled_input)[0]
            
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(5, len(cluster_songs)))
            
            song_list_str = "\n".join([f"- {row['track_name']} (ศิลปิน: {row['artists']})" for _, row in sampled_songs.iterrows()])
            
            # ให้ Gemini แต่งคำพูด
            prompt = f"คุณคือ 'DJ AI' ผู้ใช้บอกความรู้สึกว่า: '{mood_text}' เพลงที่เลือกคือ: {song_list_str} จงเขียนแนะนำสั้นๆ ภาษาไทย เป็นกันเอง"
            try:
                dj_response = model.generate_content(prompt).text
            except Exception as e:
                dj_response = "(ระบบ Gemini ขัดข้องชั่วคราว) แต่นี่คือเพลงที่เราจัดไว้ให้ครับ!"

            # บันทึกข้อมูลทั้งหมดลง Session State เพื่อนำไปแสดงผล
            st.session_state.playlist_data = {
                "mood": mood_text,
                "cluster": predicted_cluster,
                "songs_str": song_list_str,
                "dj_text": dj_response,
                "sampled_songs": sampled_songs
            }
            # รีเซ็ตสถานะการกด Feedback เป็น False เสมอเมื่อจัดเพลงใหม่
            st.session_state.feedback_submitted = False

# ==========================================
# ส่วนแสดงผลลัพธ์ (จะแสดงเมื่อมีข้อมูลใน Session State)
# ==========================================
if st.session_state.playlist_data:
    data = st.session_state.playlist_data
    
    st.success("จัดเพลงเสร็จเรียบร้อย!")
    st.markdown("### 💬 ข้อความจาก DJ AI (Powered by Google Gemini)")
    st.info(data["dj_text"])
    
    st.markdown(f"### 🎼 รายชื่อเพลง (กลุ่มดนตรีที่ {data['cluster']})")
    st.text(data["songs_str"])

    # --- ส่วนแสดง Radar Chart ---
    st.markdown("---")
    avg_energy = data["sampled_songs"]['energy'].mean()
    avg_valence = data["sampled_songs"]['valence'].mean()
    avg_tempo_scaled = data["sampled_songs"]['tempo'].mean() / 200.0 

    categories = ['ความมันส์ (Energy)', 'ความสดใส (Valence)', 'ความเร็ว (Tempo)']
    values = [avg_energy, avg_valence, avg_tempo_scaled]
    categories.append(categories[0]) 
    values.append(values[0])

    fig = go.Figure(data=go.Scatterpolar(
        r=values, theta=categories, fill='toself', fillcolor='rgba(29, 185, 84, 0.5)', line_color='#1DB954'
    ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, title="📊 ระดับอารมณ์ของ Playlist นี้")
    st.plotly_chart(fig, use_container_width=True)

    # --- ส่วนระบบ Feedback ---
    st.markdown("---")
    st.markdown("### 📝 คุณชอบ Playlist นี้ไหม?")
    
    # ถ้ายังไม่ได้กด Feedback ให้แสดงปุ่ม
    if not st.session_state.feedback_submitted:
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("👍 โดนใจสุดๆ", use_container_width=True):
                save_feedback(data["mood"], data["cluster"], "Like")
                st.session_state.feedback_submitted = True
                st.rerun() # สั่งรีเฟรชหน้าเว็บ 1 ครั้งเพื่อซ่อนปุ่ม
        with col2:
            if st.button("👎 ไม่ค่อยเข้ากัน", use_container_width=True):
                save_feedback(data["mood"], data["cluster"], "Dislike")
                st.session_state.feedback_submitted = True
                st.rerun()
    else:
        # ถ้ากดไปแล้ว ให้แสดงคำขอบคุณแทนปุ่ม
        st.success("💖 ขอบคุณสำหรับเสียงตอบรับครับ! ระบบบันทึกข้อมูลเพื่อนำไปพัฒนา AI เรียบร้อยแล้ว")