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
# 4. ฟังก์ชันประมวลผลข้อมูล
# ==========================================
def clean_json_string(text):
    """คลีนข้อความจาก Gemini ให้เป็น JSON สตริงบริสุทธิ์"""
    if not text:
        return ""
    clean_text = text.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()
    return clean_text

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
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง"]): 
        return 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น"]): 
        return 0.8, 0.8, 130.0
    return 0.5, 0.5, 100.0

@st.cache_data(ttl=3600)
def get_spotify_track_info(track_name, artist_name):
    """ดึงรูปปก, ตัวอย่างเสียง (Audio Preview), และลิงก์ฟังเพลง โดยลองจากหลาย Source"""
    clean_title = re.sub(r'[\(\[\-\~].*?[\)\]\-\~]', '', str(track_name)).strip()
    clean_artist = str(artist_name).split(',')[0].strip()
    
    # 1. ลองดึงจาก iTunes API
    try:
        query = f"{clean_title} {clean_artist}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1&entity=song"
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
        url_d = f"https://api.deezer.com/search?q={requests.utils.quote(query_d)}&limit=1"
        res_d = requests.get(url_d, timeout=4)
        if res_d.status_code == 200:
            data_d = res_d.json()
            if data_d.get('data') and len(data_d['data']) > 0:
                t = data_d['data'][0]
                img = t.get('album', {}).get('cover_xl') or t.get('album', {}).get('cover_big')
                prev = t.get('preview', None)
                link = t.get('link', None)
                if img:
                    return img, prev, link
    except Exception:
        pass

    return None, None, None

def get_song_reason(data, index, row):
    """คำนวณและสร้างเหตุผลรายเพลงให้ตรงกับเพลงแบบ 100%"""
    reasons_list = data.get("song_reasons", [])
    
    # 1. ดึงจาก Gemini AI ตาม Index
    if isinstance(reasons_list, list) and index < len(reasons_list):
        item = reasons_list[index]
        if isinstance(item, dict):
            r = item.get("reason")
            tag = item.get("mood_tag", "#DJChoice")
            if r: 
                return r, tag

    # 2. คำนวณแบบ Dynamic จาก Audio Features ของเพลงนั้นๆ
    energy = row.get('energy', 0.5)
    valence = row.get('valence', 0.5)
    tempo = row.get('tempo', 100)
    
    if energy > 0.7:
        reason_fb = f"เพลงนี้มีจังหวะพลังงานสูง (Energy: {energy:.2f}, Tempo: {int(tempo)} BPM) ช่วยปลุกความสดใส เติมไฟให้อารมณ์ของคุณกระปรี้กระเปร่าขึ้นทันที"
        tag_fb = "🔥 #เพิ่มพลังใจ"
    elif valence < 0.35:
        reason_fb = f"ทำนองนุ่มลึกในโทนอารมณ์นี้ (Valence: {valence:.2f}) จะอยู่เป็นเพื่อนโอบกอดความรู้สึกของคุณในห้วงเวลาที่ต้องการความเข้าใจ"
        tag_fb = "🌙 #โอบกอดอารมณ์"
    elif valence > 0.65:
        reason_fb = f"เสียงดนตรีฟีลกู้ด (Valence: {valence:.2f}) เพิ่มรอยยิ้ม เติมบรรยากาศความสุขและความเบาสบายให้วันของคุณ"
        tag_fb = "✨ #ฟีลกู้ดชิลๆ"
    else:
        reason_fb = f"จังหวะกำลังดีปานกลาง ({int(tempo)} BPM) ผสมผสานดนตรีที่สมดุล ให้ความรู้สึกผ่อนคลายและเข้ากับบรรยากาศได้อย่างลงตัว"
        tag_fb = "🍃 #ผ่อนคลายสมดุล"
        
    return reason_fb, tag_fb

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
# 5. จัดการ Session State
# ==========================================
if 'playlist_data' not in st.session_state:
    st.session_state.playlist_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False
if 'current_card_index' not in st.session_state:
    st.session_state.current_card_index = 0

# ==========================================
# 6. ส่วนรับข้อมูลจากผู้ใช้ (UI)
# ==========================================
with st.container():
    st.markdown("##### 🎙️ เล่าความรู้สึกของคุณผ่านเสียงหรือพิมพ์ข้อความ")
    
    text_from_mic = speech_to_text(
        language='th-TH', 
        start_prompt="🎙 กดเพื่อพูดความรู้สึก", 
        stop_prompt="🛑 กำลังฟัง... (กดเพื่อหยุด)", 
        just_once=False,
        key='STT'
    )

    default_text = text_from_mic if text_from_mic else ""
    mood_text = st.text_area("ความรู้สึกของคุณ:", value=default_text, placeholder="เช่น วันนี้เลิกงานแล้ว เหนื่อยมากๆ อยากหาเพลงชิลๆ ฟังผ่อนคลาย...", height=95)

    num_songs = st.slider("🎵 จำนวนเพลงที่ต้องการสุ่มจัด:", min_value=3, max_value=12, value=5, step=1)

    if st.button("✨ ให้ AI DJ จัดเพลงให้ทันที", type="primary", use_container_width=True):
        if not mood_text:
            st.warning("กรุณาพิมพ์หรือพูดความรู้สึกของคุณก่อนครับ")
        else:
            with st.spinner("🎧 DJ AI กำลังอ่านใจและวิเคราะห์อารมณ์ดนตรี..."):
                t_energy, t_valence, t_tempo = analyze_mood_with_gemini(mood_text)
                
                try:
                    user_df = pd.DataFrame([[0.5, t_energy, t_valence, t_tempo]], columns=scaler.feature_names_in_)
                    scaled_input = scaler.transform(user_df)
                except AttributeError:
                    user_features = [[0.5, t_energy, t_valence, t_tempo]]
                    scaled_input = scaler.transform(user_features)

                predicted_cluster = kmeans.predict(scaled_input)[0]
                cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
                sampled_songs = cluster_songs.sample(min(num_songs, len(cluster_songs))).reset_index(drop=True)
                
                song_items_prompt = []
                for idx, r in sampled_songs.iterrows():
                    song_items_prompt.append(f"เพลงลำดับ {idx}: '{r['track_name']}' โดย {r['artists']}")
                song_list_str = "\n".join(song_items_prompt)

                dj_response = f"จัดบทเพลงเซ็ตพิเศษตามอารมณ์ '{mood_text[:20]}...' มาให้คุณฟังแล้วครับ!"
                song_reasons = []

                if model:
                    prompt_dj = (
                        "คุณคือ 'DJ AI' ผู้เชี่ยวชาญด้านดนตรีสไตล์เป็นกันเองและใส่ใจผู้ฟัง\n"
                        f"ผู้ใช้บอกความรู้สึกว่า: '{mood_text}'\n\n"
                        f"เพลงที่จัดมาทั้งหมด {len(sampled_songs)} เพลง มีดังนี้:\n"
                        f"{song_list_str}\n\n"
                        "จงตอบกลับในรูปแบบ JSON โครงสร้างนี้เท่านั้น:\n"
                        "{\n"
                        '  "dj_text": "คำทักทายภาพรวมจาก DJ AI พูดถึงอารมณ์รวมสั้นๆ ภาษาไทย เป็นกันเอง",\n'
                        '  "reasons": [\n'
                        "    {\n"
                        '      "id": 0,\n'
                        '      "mood_tag": "#แท็กอารมณ์สั้นๆ",\n'
                        '      "reason": "เหตุผลสั้นๆ 1-2 ประโยคว่าทำไมเพลงลำดับ 0 ถึงเข้ากับอารมณ์นี้"\n'
                        "    }\n"
                        "  ]\n"
                        "}"
                    )
                    
                    try:
                        response = model.generate_content(
                            prompt_dj,
                            generation_config={"response_mime_type": "application/json"}
                        )
                        clean_text = clean_json_string(response.text)
                        dj_data = json.loads(clean_text)
                        dj_response = dj_data.get("dj_text", dj_response)
                        song_reasons = dj_data.get("reasons", [])
                    except Exception:
                        pass

                st.session_state.playlist_data = {
                    "mood": mood_text,
                    "cluster": predicted_cluster,
                    "dj_text": dj_response,
                    "song_reasons": song_reasons,
                    "sampled_songs": sampled_songs,
                    "features": {"energy": t_energy, "valence": t_valence, "tempo": t_tempo}
                }
                st.session_state.feedback_submitted = False
                st.session_state.current_card_index = 0

# ==========================================
# 7. ส่วนแสดงผลลัพธ์การ์ดเพลงอนิเมชัน (Card View)
# ==========================================
if st.session_state.playlist_data:
    data = st.session_state.playlist_data
    songs = data["sampled_songs"]
    total_songs = len(songs)

    st.markdown("---")
    
    # คำทักทายภาพรวมจาก DJ AI + Animated Equalizer
    st.markdown(f"""
    <div class="dj-speech-box">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <span class="dj-badge">🤖 DJ AI Message</span>
            <div class="eq-container">
                <span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span>
            </div>
        </div>
        <div style="font-size: 1.1rem; line-height: 1.6; font-weight: 500; margin-top: 10px; color: #F8FAFC;">
            "{data['dj_text']}"
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ปุ่มสลับโหมดการดู
    view_mode = st.radio(
        "รูปแบบการแสดงผล:", 
        ["🃏 มุมมองการ์ดสลับ (Card Switcher)", "📋 รายการทั้งหมด (Grid View)"], 
        horizontal=True
    )

    if "มุมมองการ์ดสลับ" in view_mode:
        # --- 🃏 ระบบการ์ดสลับเพลงแบบอนิเมชัน ---
        
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        
        with nav_col1:
            if st.button("⬅️ เพลงก่อนหน้า", use_container_width=True, key="btn_prev"):
                st.session_state.current_card_index = (st.session_state.current_card_index - 1) % total_songs
                st.rerun()

        with nav_col2:
            st.markdown(
                f"<div style='text-align: center; font-size: 1.1rem; font-weight: 700; color: #00F2FE; margin-top: 5px;'>"
                f"🎵 เพลงที่ {st.session_state.current_card_index + 1} จาก {total_songs}</div>", 
                unsafe_allow_html=True
            )

        with nav_col3:
            if st.button("เพลงถัดไป ➡", use_container_width=True, key="btn_next"):
                st.session_state.current_card_index = (st.session_state.current_card_index + 1) % total_songs
                st.rerun()

        # ดึงข้อมูลเพลงปัจจุบัน
        current_idx = st.session_state.current_card_index
        row = songs.iloc[current_idx]
        track_name = row['track_name']
        artist_name = row['artists']
        
        img_url, preview_url, spot_url = get_spotify_track_info(track_name, artist_name)
        reason, mood_tag = get_song_reason(data, current_idx, row)

        # แสดงผลการ์ดเพลงสลับพร้อมแผ่นเสียง 3D
        st.markdown('<div class="song-card-animated">', unsafe_allow_html=True)
        
        card_col1, card_col2 = st.columns([1.1, 1.9])
        
        with card_col1:
            if img_url:
                st.markdown(f"""
                <div class="album-art-wrapper">
                    <div class="vinyl-disk"><div class="vinyl-center"></div></div>
                    <img src="{img_url}" class="album-cover-img" />
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="album-art-wrapper">
                    <div class="vinyl-disk"><div class="vinyl-center"></div></div>
                    <div class="album-cover-placeholder">
                        <div style="font-size: 2.2rem; margin-bottom: 5px;">💿</div>
                        <div style="font-weight: 700; color: #00F2FE; font-size: 0.9rem;">{track_name[:18]}</div>
                        <div style="color: #94A3B8; font-size: 0.8rem;">{artist_name[:18]}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        with card_col2:
            st.markdown(f'<span class="mood-tag-badge">{mood_tag}</span>', unsafe_allow_html=True)
            st.markdown(f"<h2 style='margin-top:0px; margin-bottom: 5px;'>{track_name}</h2>", unsafe_allow_html=True)
            st.markdown(f"🎤 **ศิลปิน:** `{artist_name}`")
            
            st.markdown(f"""
            <div class="reason-box">
                💡 <b>มุมมอง DJ สำหรับเพลงนี้ ({current_idx + 1}/{total_songs}):</b><br/>
                {reason}
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            if preview_url:
                st.audio(preview_url, format="audio/mp3")
            if spot_url:
                st.markdown(f"[🔗 เปิดฟังเวอร์ชันเต็มบนเว็บ/แอป]({spot_url})")

        st.markdown('</div>', unsafe_allow_html=True)

        # แถบ Quick Pills เลือกสลับการ์ดด่วน
        tab_titles = [f"🎵 {i+1}. {songs.iloc[i]['track_name'][:12]}..." if len(songs.iloc[i]['track_name']) > 12 else f"🎵 {i+1}. {songs.iloc[i]['track_name']}" for i in range(total_songs)]
        selected_tab = st.pills("เลือกสลับการ์ดเพลงด่วน:", tab_titles, default=tab_titles[current_idx], key="pills_nav")
        if selected_tab:
            selected_index = tab_titles.index(selected_tab)
            if selected_index != st.session_state.current_card_index:
                st.session_state.current_card_index = selected_index
                st.rerun()

    else:
        # --- 📋 มุมมองรายการทั้งหมด (Grid View) ---
        for i, row in songs.iterrows():
            track_name = row['track_name']
            artist_name = row['artists']
            img_url, preview_url, spot_url = get_spotify_track_info(track_name, artist_name)
            reason, mood_tag = get_song_reason(data, i, row)

            st.markdown('<div class="song-card-animated">', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2.5])
            
            with c1:
                if img_url:
                    st.markdown(f"""
                    <div class="album-art-wrapper">
                        <div class="vinyl-disk"><div class="vinyl-center"></div></div>
                        <img src="{img_url}" class="album-cover-img" style="width: 140px; height: 140px;" />
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="album-art-wrapper">
                        <div class="vinyl-disk"><div class="vinyl-center"></div></div>
                        <div class="album-cover-placeholder" style="width: 140px; height: 140px;">
                            <div style="font-size: 1.8rem;">💿</div>
                            <div style="font-size: 0.75rem; color: #00F2FE;">{track_name[:12]}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            with c2:
                st.markdown(f'<span class="mood-tag-badge">{mood_tag}</span>', unsafe_allow_html=True)
                st.subheader(f"{i+1}. {track_name}")
                st.markdown(f"🎤 **ศิลปิน:** `{artist_name}`")
                st.markdown(f"<div class='reason-box'>💡 <b>มุมมอง DJ:</b> {reason}</div>", unsafe_allow_html=True)
                st.write("")
                if preview_url:
                    st.audio(preview_url, format="audio/mp3")
                if spot_url:
                    st.markdown(f"[🎧 คลิกฟังเพลงเต็ม]({spot_url})")
                    
            st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # 8. กราฟวิเคราะห์อารมณ์ & Feedback
    # ==========================================
    st.markdown("---")
    
    col_chart, col_feed = st.columns([1.2, 1])
    
    with col_chart:
        f_energy = data["features"]["energy"]
        f_valence = data["features"]["valence"]
        f_tempo_scaled = data["features"]["tempo"] / 200.0

        categories = ['ความมันส์ (Energy)', 'ความสดใส (Valence)', 'ความเร็ว (Tempo)']
        values = [f_energy, f_valence, f_tempo_scaled]
        categories.append(categories[0]) 
        values.append(values[0])

        fig = go.Figure(data=go.Scatterpolar(
            r=values, theta=categories, fill='toself', fillcolor='rgba(0, 242, 254, 0.25)', line_color='#00F2FE'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])), 
            showlegend=False, 
            title="📊 กราฟวิเคราะห์โทนอารมณ์ดนตรี",
            margin=dict(l=35, r=35, t=35, b=35)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_feed:
        st.markdown("### 📝 ถูกใจ Playlist นี้ไหม?")
        st.write("เสียงตอบรับของคุณจะช่วยให้ AI DJ ปรับปรุงการคัดสรรเพลงในครั้งถัดไปให้ดียิ่งขึ้น")
        
        if not st.session_state.feedback_submitted:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("👍 โดนใจมาก", use_container_width=True):
                    save_feedback(data["mood"], data["cluster"], "Like")
                    st.session_state.feedback_submitted = True
                    st.rerun()
            with btn_col2:
                if st.button("👎 ยังไม่ค่อยโดน", use_container_width=True):
                    save_feedback(data["mood"], data["cluster"], "Dislike")
                    st.session_state.feedback_submitted = True
                    st.rerun()
        else:
            st.success("💖 ขอบคุณสำหรับคำติชมครับ! ระบบบันทึกข้อมูลเรียบร้อยแล้ว")
