import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
from datetime import datetime
from streamlit_mic_recorder import speech_to_text

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
    model = genai.GenerativeModel('gemini-3.6-flash')
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
# 4. ฟังก์ชันเบื้องหลัง (Gemini + ดึงข้อมูลเพลง)
# ==========================================
def analyze_mood_with_gemini(text):
    """ใช้ Gemini แปลงความรู้สึกเป็นค่า Energy, Valence, Tempo"""
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
    """ระบบสำรองหาก Gemini ขัดข้อง"""
    text = text.lower()
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง"]): return 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น"]): return 0.8, 0.8, 130.0
    return 0.5, 0.5, 100.0

@st.cache_data(ttl=3600)
def get_spotify_track_info(track_name, artist_name):
    """
    ดึงรูปปก, ตัวอย่างเพลง (Audio Preview), และลิงก์ฟังเพลง
    (ใช้ Search API เพื่อค้นหาปกเพลงและไฟล์ตัวอย่างเสียง)
    """
    try:
        query = f"{track_name} {artist_name}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1&entity=song"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('resultCount', 0) > 0:
                track = data['results'][0]
                img_url = track.get('artworkUrl100', '').replace('100x100bb', '300x300bb') # ปรับรูปให้ชัดขึ้น
                preview_url = track.get('previewUrl', None)
                spot_url = track.get('trackViewUrl', None)
                return img_url, preview_url, spot_url
    except Exception:
        pass
    return None, None, None

def save_feedback(mood, cluster, feedback_type):
    try:
        url = st.secrets.get("SHEETS_WEB_APP_URL", "")
        if url:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {"timestamp": timestamp, "mood": mood, "cluster": str(cluster), "feedback": feedback_type}
            requests.post(url, json=payload)
    except Exception:
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
st.markdown("### 🗣️️ เล่าความรู้สึกของคุณ")

# ปุ่มกดพูด (แปลงเสียงเป็นข้อความ)
text_from_mic = speech_to_text(
    language='th-TH', 
    start_prompt="🎙️ กดเพื่อพูด (พูดเสร็จให้กดซ้ำอีกรอบ)", 
    stop_prompt="🛑 กำลังฟัง... (กดเพื่อหยุด)", 
    just_once=False,
    key='STT'
)

# กล่องรับข้อความ
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
            except Exception:
                dj_response = "(ระบบ Gemini ขัดข้องชั่วคราว) แต่นี่คือเพลงที่เราจัดไว้ให้ครับ!"

            st.session_state.playlist_data = {
                "mood": mood_text,
                "cluster": predicted_cluster,
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
    
    st.markdown(f"### 🎼 รายชื่อเพลงแนะนำ (กลุ่มดนตรีที่ {data['cluster']})")

    # วนลูปแสดงเพลงทีละบรรทัด พร้อมรูปปก 🌟
    for _, row in data["sampled_songs"].iterrows():
        # ดึงข้อมูลจาก Spotify / Store
        img_url, preview_url, spot_url = get_spotify_track_info(row['track_name'], row['artists'])
        
        # แบ่งหน้าจอเป็น 2 คอลัมน์ (ซ้ายรูป ขวาข้อความ)
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if img_url:
                st.image(img_url, width=120)
            else:
                st.write("💿 No Image")
                
        with col2:
            st.subheader(row['track_name'])
            st.write(f"🎤 ศิลปิน: {row['artists']}")
            
            if spot_url:
                st.markdown(f"[🎧 ฟังเพลงเต็มคลิกที่นี่]({spot_url})")
            if preview_url:
                st.audio(preview_url, format="audio/mp3")
                
        st.divider() # เส้นคั่นแต่ละเพลง

    # ----------------------------------------
    # กราฟ Radar Chart
    # ----------------------------------------
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
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, title="📊 ระดับอารมณ์ที่คุณต้องการ (วิเคราะห์โดย AI)")
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------
    # ระบบ Feedback
    # ----------------------------------------
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
        st.success("💖 ขอบคุณสำหรับเสียงตอบรับครับ! ข้อมูลถูกบันทึกลงฐานข้อมูลเรียบร้อยแล้ว")