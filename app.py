import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
import json
import re
from datetime import datetime
from streamlit_mic_recorder import speech_to_text

# ==========================================
# 1. ตั้งค่าหน้าเว็บ + Custom CSS & Animations
# ==========================================
st.set_page_config(
    page_title="AI DJ Mood Matcher", 
    page_icon="🎧",
    layout="centered"
)

# ตกแต่ง CSS และ อนิเมชันเต็มรูปแบบ
st.markdown("""
<style>
    /* ซ่อน Header / Footer ดั้งเดิม */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Keyframe Animations */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(25px) scale(0.97); }
        to { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes pulseGlow {
        0% { box-shadow: 0 0 12px rgba(0, 242, 254, 0.2); }
        50% { box-shadow: 0 0 28px rgba(0, 242, 254, 0.55), 0 0 10px rgba(155, 81, 224, 0.4); }
        100% { box-shadow: 0 0 12px rgba(0, 242, 254, 0.2); }
    }

    @keyframes rotateVinyl {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    @keyframes floatHeader {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-5px); }
        100% { transform: translateY(0px); }
    }

    @keyframes equalBlink {
        0%, 100% { height: 4px; }
        50% { height: 18px; }
    }

    /* หัวข้อหลักแบบ Gradient & Floating */
    .gradient-header {
        background: linear-gradient(135deg, #00F2FE 0%, #4FACFE 50%, #9B51E0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.7rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 5px;
        animation: floatHeader 4s ease-in-out infinite;
    }
    .sub-title {
        text-align: center;
        color: #A0AEC0;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }

    /* กล่องข้อความจาก DJ AI */
    .dj-speech-box {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.75) 100%);
        border: 1px solid rgba(0, 242, 254, 0.35);
        border-radius: 20px;
        padding: 22px;
        margin-bottom: 25px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        animation: fadeInUp 0.5s ease-out;
    }
    .dj-badge {
        background: linear-gradient(90deg, #00F2FE, #4FACFE);
        color: #0F172A;
        font-weight: 800;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.82rem;
        display: inline-block;
    }

    /* Animated Equalizer Bars */
    .eq-container {
        display: inline-flex;
        align-items: flex-end;
        height: 18px;
        margin-left: 10px;
        vertical-align: middle;
    }
    .eq-bar {
        width: 3.5px;
        margin: 0 2px;
        background: linear-gradient(to top, #00F2FE, #9B51E0);
        border-radius: 3px;
        animation: equalBlink 1.1s ease-in-out infinite alternate;
    }
    .eq-bar:nth-child(1) { animation-delay: 0.1s; }
    .eq-bar:nth-child(2) { animation-delay: 0.4s; }
    .eq-bar:nth-child(3) { animation-delay: 0.2s; }
    .eq-bar:nth-child(4) { animation-delay: 0.5s; }

    /* การ์ดเพลงหลักสไตล์ Animated Glassmorphism */
    .song-card-animated {
        background: rgba(30, 41, 59, 0.75);
        border: 1px solid rgba(0, 242, 254, 0.25);
        border-radius: 22px;
        padding: 24px;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(14px);
        margin-top: 10px;
        margin-bottom: 15px;
        animation: fadeInUp 0.45s ease-out;
        transition: all 0.3s ease;
    }
    .song-card-animated:hover {
        border-color: rgba(0, 242, 254, 0.6);
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 242, 254, 0.2);
    }

    /* แฮชแท็กอารมณ์เรืองแสง */
    .mood-tag-badge {
        background: linear-gradient(90deg, #9B51E0, #00F2FE);
        color: #FFFFFF;
        font-size: 0.82rem;
        font-weight: 700;
        padding: 4px 14px;
        border-radius: 14px;
        display: inline-block;
        margin-bottom: 12px;
        animation: pulseGlow 2.5s infinite;
    }

    .reason-box {
        background: rgba(15, 23, 42, 0.7);
        border-left: 4px solid #00F2FE;
        border-radius: 10px;
        padding: 14px 18px;
        margin-top: 12px;
        font-size: 0.95rem;
        color: #F1F5F9;
        line-height: 1.5;
    }

    /* แผ่นเสียงหมุน 3D (Vinyl Disk Component) */
    .album-art-wrapper {
        position: relative;
        width: 210px;
        height: 210px;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .vinyl-disk {
        position: absolute;
        right: -18px;
        width: 180px;
        height: 180px;
        border-radius: 50%;
        background: radial-gradient(circle, #111 18%, #222 19%, #000 35%, #181818 50%, #000 70%, #222 100%);
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.8), inset 0 0 8px rgba(255, 255, 255, 0.25);
        animation: rotateVinyl 8s linear infinite;
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .vinyl-center {
        width: 55px;
        height: 55px;
        border-radius: 50%;
        background: linear-gradient(135deg, #00F2FE, #9B51E0);
        border: 3px solid #111;
    }
    .album-cover-img {
        position: relative;
        z-index: 2;
        width: 190px;
        height: 190px;
        object-fit: cover;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.65);
        transition: transform 0.3s ease;
    }
    .album-cover-img:hover {
        transform: scale(1.03) rotate(-1deg);
    }
    .album-cover-placeholder {
        position: relative;
        z-index: 2;
        width: 190px;
        height: 190px;
        border-radius: 16px;
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid rgba(0, 242, 254, 0.3);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.65);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 15px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="gradient-header">🎧 AI DJ Mood Matcher</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">บอกความรู้สึกของคุณ แล้วให้ AI DJ คัดสรรบทเพลงพร้อมมุมมองเฉพาะคุณ</div>', unsafe_allow_html=True)

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ API (Gemini & Secrets)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-3.6-flash')
    else:
        model = None
except Exception:
    model = None

# ==========================================
# 3. โหลดโมเดล Machine Learning
# ==========================================
@st.cache_resource
def load_models():
    km = joblib.load('kmeans_model.pkl')
    sc = joblib.load('scaler.pkl')
    df = pd.read_csv('spotify_clustered.csv')
    return km, sc, df

try:
    kmeans, scaler, df_songs = load_models()
except Exception:
    st.error("🚨 ไม่พบไฟล์โมเดล .pkl หรือ .csv กรุณาอัปโหลดขึ้น GitHub ให้ครบ")
    st.stop()

# ==========================================
# 4. ฟังก์ชันประมวลผลข้อมูล (Gemini + Multi-API Image Search)
# ==========================================
def clean_json_string(text):
    """คลีนข้อความจาก Gemini ให้เป็น JSON สตริงบริสุทธิ์"""
    if not text:
        return ""
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```$', '', text, flags=re.MULTILINE)
    return text.strip()

def analyze_mood_with_gemini(text):
    """แปลงความรู้สึกเป็นค่า Energy, Valence, Tempo"""
    if not model:
        return fallback_analyze_mood(text)
        
    prompt = f"""
    คุณคือนักจิตวิทยาทางดนตรี จงวิเคราะห์ข้อความต่อไปนี้แล้วแปลงเป็นค่าทางดนตรี 3 ค่า
    1. Energy (0.0 ถึง 1.0): 0 คือสงบ/อ่อนล้า, 1 คือมันส์/พลังงานล้น
    2. Valence (0.0 ถึง 1.0): 0 คือเศร้า/หดหู่/โกรธ, 1 คือมีความสุข/สดใส
    3. Tempo (60.0 ถึง 200.0): ความเร็วของเพลง (BPM)

    ข้อความผู้ใช้: "{text}"

    ตอบกลับเป็นตัวเลข 3 ตัว คั่นด้วยเครื่องหมายจุลภาค (,) เท่านั้น เช่น: 0.8,0.9,130
    """
    try:
        response = model.generate_content(prompt)
        clean_text = re.sub(r'[^0-9.,]', '', response.text).strip()
        values = clean_text.split(',')
        return float(values[0].strip()), float(values[1].strip()), float(values[2].strip())
    except Exception:
        return fallback_analyze_mood(text)

def fallback_analyze_mood(text):
    text = text.lower()
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง"]): return 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น"]): return 0.8, 0.8, 130.0
    return 0.5, 0.5, 100.0

@st.cache_data(ttl=3600)
def get_spotify_track_info(track_name, artist_name):
    """ดึงรูปปก, ตัวอย่างเสียง (Audio Preview), และลิงก์ฟังเพลง โดยลองจากหลาย Source"""
    clean_title = re.sub(r'[\(\[\-\~].*?[\)\]\-\~]', '', str(track_name)).strip()
    clean_artist = str(artist_name).split(',')[0].strip()
    
    # 1. ลองดึงจาก iTunes API
    try:
        query = f"{clean_title} {clean_artist}"
        url = f"[https://itunes.apple.com/search?term=](https://itunes.apple.com/search?term=){requests.utils.quote(query)}&limit=1&entity=song"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if data.get('resultCount', 0) > 0:
                t = data['results'][0]
                img = t.get('artworkUrl100', '').replace('100x100bb', '500x500bb')
                prev = t.get('previewUrl', None)
                link = t.get('trackViewUrl', None)
                if img:
                    return img, prev, link
    except Exception:
        pass

    # 2. สำรองด้วย Deezer API
    try:
        query_d = f"{clean_title} {clean_artist}"
        url_d = f"[https://api.deezer.com/search?q=](https://api.deezer.com/search?q=){requests.utils.quote(query_d)}&limit=1"
        res_d = requests.get(url_d, timeout=4)
        if res_d.status_code == 200:
            data_d = res_d.json()
            if data_d.get('data') and len(data_d['data']) > 0:
                t = data_d['data'][0]
                img = t.get('album', {}).get('cover_xl') or t.get('album', {}).get('cover_big')
                prev = t.get('preview', None)
                link = t.get('link', None)
                if img:
                    return img, prev
