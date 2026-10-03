import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
from datetime import datetime
from streamlit_mic_recorder import speech_to_text # นำเข้าระบบไมโครโฟน

# ==========================================
# 1. ตั้งค่าหน้าเว็บ
# ==========================================
st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")
st.markdown("พิมพ์บอกความรู้สึก หรือ **กดไมค์เพื่อพูด** แล้วให้ AI DJ จัดเพลงให้!")

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ API (Gemini & Google Sheets)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("🚨 ไม่พบ API Key! กรุณาตั้งค่า GOOGLE_API_KEY ใน Streamlit Secrets")
    st.stop()

# ==========================================
# 3. ฟังก์ชันโหลดโมเดล Machine Learning
# ==========================================
@st.cache_resource
def load_models():
    km = joblib.load('kmeans_model.pkl')
    sc = joblib.load('scaler.pkl')
    df = pd.read_csv('spotify_clustered.csv')
    return km, sc, df

try:
    kmeans, scaler, df_songs = load_models()
except Exception as e:
    st.error("🚨 ไม่พบไฟล์โมเดล .pkl หรือ .csv กรุณาอัปโหลดขึ้น GitHub ให้ครบ")
    st.stop()

# ==========================================
# 4. ฟังก์ชันเบื้องหลัง (อัปเกรดความฉลาดด้วย Gemini)
# ==========================================
def analyze_mood_with_gemini(text):
    prompt = f"""
    คุณคือนักจิตวิทยาทางดนตรี จงวิเคราะห์ข้อความต่อไปนี้แล้วแปลงเป็นค่าทางดนตรี 3 ค่า
    1. Energy (0.0 ถึง 1.0): 0 คือสงบ/อ่อนล้า, 1 คือมันส์/พลังงานล้น
    2. Valence (0.0 ถึง 1.0): 0 คือเศร้า/หดหู่/โกรธ, 1 คือมีความสุข/สดใส
    3. Tempo (60.0 ถึง 200.0): ความเร็วของเพลง (BPM)

    ข้อความผู้ใช้: "{text}"

    จงตอบกลับมาเป็นตัวเลข 3 ตัว คั่นด้วยเครื่องหมายจุลภาค (,) เท่านั้น ห้ามมีตัวอักษรอื่นเด็ดขาด
    ตัวอย่างการตอบ: 0.8,0.9,130
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace('`', '').strip()
        values = clean_text.split(',')
        return float(values[0].strip()), float(values[1].strip()), float(values[2].strip())
    except Exception as e:
        return fallback_analyze_mood(text)

def fallback_analyze_mood(text):
    text = text.lower()
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง"]): return 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น"]): return 0.8, 0.8, 130.0
    return 0.5, 0.5, 100.0

def save_feedback(mood, cluster, feedback_type):
    try:
        url = st.secrets.get("SHEETS_WEB_APP_URL", "")
        if url:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {"timestamp": timestamp, "mood": mood, "cluster": str(cluster), "feedback": feedback_type}
            requests.post(url, json=payload)
    except:
        pass

# ==========================================
# 5. ระบบความจำ (Session State)
# ==========================================
if 'playlist_data' not in st.session_state:
    st.session_state.playlist_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False

# ==========================================
# 6. ส่วน UI หน้าเว็บ (ไมโครโฟน + กล่องข้อความ)
# ==========================================
st.markdown("### 🗣️ เล่าความรู้สึกของคุณ")

# 6.1 ปุ่มกดพูด (แปลงเสียงเป็นข้อความ)
text_from_mic = speech_to_text(
    language='th-TH', 
    start_prompt="🎙️ กดเพื่อพูด (พูดเสร็จให้กดซ้ำอีกรอบ)", 
    stop_prompt="🛑 กำลังฟัง... (กดเพื่อหยุด)", 
    just_once=False,
    key='STT'
)

# 6.2 กล่องรับข้อความ (ถ้าระบบได้ยินเสียง จะเอาข้อความมาใส่ในกล่องนี้อัตโนมัติ)
default_text = text_from_mic if text_from_mic else ""
mood_text = st.text_area("หรือพิมพ์ความรู้สึกที่นี่:", value=default_text, placeholder="เช่น วันนี้ฝนตก เหงาจังเลย...")

# ปุ่มประมวลผล
if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", use_container_width=True):
    if not mood_text:
        st.warning("กรุณาพิมพ์หรือพูดความรู้สึกของคุณก่อนครับ")
    else:
        with st.spinner("DJ (Gemini) กำลังตีความความรู้สึกของคุณ..."):
            t_energy, t_valence, t_tempo = analyze_mood_with_gemini(mood_text)
            
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            scaled_input = scaler.transform(user_features)
            predicted_cluster = kmeans.predict(scaled_input)[0]
            
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(5, len(cluster_songs)))
            song_list_str = "\n".join([f"- {row['track_name']} (ศิลปิน: {row['artists']})" for _, row in sampled_songs.iterrows()])
            
            prompt_dj = f"คุณคือ 'DJ AI' ผู้ใช้บอกว่า: '{mood_text}' เพลงที่เลือกคือ: {song_list_str} จงทักทายสั้นๆ ภาษาไทย เป็นกันเอง"
            try:
                dj_response = model.generate_content(prompt_dj).text
            except:
                dj_response = "(ระบบ Gemini ขัดข้องชั่วคราว) แต่นี่คือเพลงที่เราจัดไว้ให้ครับ!"

            st.session_state.playlist_data = {
                "mood": mood_text,
                "cluster": predicted_cluster,
                "songs_str": song_list_str,
                "dj_text": dj_response,
                "sampled_songs": sampled_songs,
                "features": {"energy": t_energy, "valence": t_valence, "tempo": t_tempo}
            }
            st.session_state.feedback_submitted = False

# ==========================================
# 7. ส่วนแสดงผลลัพธ์
# ==========================================
if st.session_state.playlist_data:
    data = st.session_state.playlist_data
    
    st.success("จัดเพลงเสร็จเรียบร้อย!")
    st.markdown("### 💬 ข้อความจาก DJ AI (Powered by Google Gemini)")
    st.info(data["dj_text"])
    
    st.markdown(f"### 🎼 รายชื่อเพลง (กลุ่มดนตรีที่ {data['cluster']})")
    st.text(data["songs_str"])

    # วาดกราฟ Radar
    st.markdown("---")
    f_energy = data["features"]["energy"]
    f_valence = data["features"]["valence"]
    f_tempo_scaled = data["features"]["tempo"] / 200.0

    categories = ['ความมันส์ (Energy)', 'ความสดใส (Valence)', 'ความเร็ว (Tempo)']
    values = [f_energy, f_valence, f_tempo_scaled]
    categories.append(categories[0]) 
    values.append(values[0])

    fig = go.Figure(data=go.Scatterpolar(
        r=values, theta=categories, fill='toself', fillcolor='rgba(29, 185, 84, 0.5)', line_color='#1DB954'
    ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, title="📊 ระดับอารมณ์ที่คุณต้องการ")
    st.plotly_chart(fig, use_container_width=True)

    # ระบบ Feedback
    st.markdown("---")
    st.markdown("### 📝 คุณชอบ Playlist นี้ไหม?")
    
    if not st.session_state.feedback_submitted:
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("👍 โดนใจสุดๆ", use_container_width=True):
                save_feedback(data["mood"], data["cluster"], "Like")
                st.session_state.feedback_submitted = True
                st.rerun()
        with col2:
            if st.button("👎 ไม่ค่อยเข้ากัน", use_container_width=True):
                save_feedback(data["mood"], data["cluster"], "Dislike")
                st.session_state.feedback_submitted = True
                st.rerun()
    else:
        st.success("💖 ขอบคุณสำหรับเสียงตอบรับครับ! ข้อมูลถูกบันทึกลงฐานข้อมูลเพื่อพัฒนา AI เรียบร้อยแล้ว")