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
# 1. ตั้งค่าหน้าเว็บ + ตกแต่ง CSS ให้ทันสมัย
# ==========================================
st.set_page_config(
    page_title="AI DJ Mood Matcher", 
    page_icon="🎧",
    layout="centered"
)

# Custom CSS ตกแต่งสไตล์ Dark Glassmorphism & Neon Accent
st.markdown("""
<style>
    /* ซ่อน Header/Footer ดั้งเดิมของ Streamlit ให้ดูคลีน */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* หัวข้อหลักแบบ Gradient Text */
    .gradient-header {
        background: linear-gradient(135deg, #00F2FE 0%, #4FACFE 50%, #00C6FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.6rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0px;
    }
    .sub-title {
        text-align: center;
        color: #A0AEC0;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }

    /* กล่องข้อความจาก DJ */
    .dj-speech-box {
        background: linear-gradient(135deg, rgba(79, 172, 254, 0.15) 0%, rgba(0, 242, 254, 0.08) 100%);
        border: 1px solid rgba(79, 172, 254, 0.3);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 25px;
        backdrop-filter: blur(10px);
    }
    .dj-badge {
        background: linear-gradient(90deg, #00F2FE, #4FACFE);
        color: #0F172A;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        display: inline-block;
        margin-bottom: 10px;
    }

    /* การ์ดเพลงสไตล์ Glassmorphism */
    .song-card-container {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(12px);
        margin-top: 10px;
        margin-bottom: 15px;
    }
    
    .reason-box {
        background: rgba(15, 23, 42, 0.6);
        border-left: 3px solid #00F2FE;
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 12px;
        font-size: 0.93rem;
        color: #E2E8F0;
    }

    /* รูปปกเพลงเอฟเฟกต์โค้งเงา */
    .album-cover-img {
        border-radius: 14px;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# หัวข้อหน้าเว็บ
st.markdown('<div class="gradient-header">🎧 AI DJ Mood Matcher</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">บอกความรู้สึกของคุณ แล้วให้ AI DJ จัดบทเพลงที่ตรงใจให้อัตโนมัติ</div>', unsafe_allow_html=True)

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ API (Gemini & Google Sheets)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
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
# 4. ฟังก์ชันประมวลผล (Gemini + iTunes API)
# ==========================================
def analyze_mood_with_gemini(text):
    """ใช้ Gemini แปลงความรู้สึกเป็นค่า Energy, Valence, Tempo"""
    if not model:
        return fallback_analyze_mood(text)
        
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
    """ดึงรูปปก, ตัวอย่างเสียง (Audio Preview), และลิงก์ฟังเพลง"""
    try:
        query = f"{track_name} {artist_name}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1&entity=song"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('resultCount', 0) > 0:
                track = data['results'][0]
                img_url = track.get('artworkUrl100', '').replace('100x100bb', '400x400bb')
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

def clean_json_string(text):
    """คลีนสตริง JSON ให้ปลอดภัยจากสัญลักษณ์โค้ดบล็อก"""
    clean_text = text.strip()
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()
    return clean_text

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
    mood_text = st.text_area("ความรู้สึกของคุณ:", value=default_text, placeholder="เช่น วันนี้เลิกงานแล้ว เหนื่อยมากๆ อยากหาเพลงชิลๆ ฟังผ่อนคลาย...", height=100)

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
                
                song_list_str = "\n".join([f"- {row['track_name']} (ศิลปิน: {row['artists']})" for _, row in sampled_songs.iterrows()])
                
                dj_response = "จัดเพลงตามอารมณ์มาให้แล้วครับ!"
                song_reasons = {}

                if model:
                    prompt_dj = f"""
                    คุณคือ 'DJ AI' ที่เข้าใจอารมณ์คนฟังอย่างลึกซึ้ง
                    ผู้ใช้บอกความรู้สึกว่า: '{mood_text}'
                    เพลงที่คัดเลือกมาให้ {len(sampled_songs)} เพลง ได้แก่:
                    {song_list_str}

                    จงตอบกลับเป็น JSON โครงสร้างตามนี้เท่านั้น:
                    {{
                      "dj_text": "ข้อความทักทายภาพรวมสั้นๆ ภาษาไทย เป็นกันเอง สนิทสนม",
                      "reasons": {{
                        "ชื่อเพลงเป๊ะๆ ตามลิสต์": "เหตุผลสั้นๆ 1-2 ประโยคภาษาไทย ว่าทำไมเพลงนี้ถึงเข้ากับอารมณ์นี้และเป็นแนวเพลงแบบไหน"
                      }}
                    }}
                    """
                    
                    try:
                        response = model.generate_content(
                            prompt_dj,
                            generation_config={"response_mime_type": "application/json"}
                        )
                        clean_text = clean_json_string(response.text)
                        
                        dj_data = json.loads(clean_text)
                        dj_response = dj_data.get("dj_text", dj_response)
                        song_reasons = dj_data.get("reasons", {})
                    except Exception:
                        dj_response = "จัดเพลงเซ็ตพิเศษตามอารมณ์ของคุณเรียบร้อยแล้วครับ มาลองฟังกันเลย!"

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
# 7. ส่วนแสดงผลลัพธ์การ์ดเพลงสลับ (Card View)
# ==========================================
if st.session_state.playlist_data:
    data = st.session_state.playlist_data
    songs = data["sampled_songs"]
    total_songs = len(songs)

    st.markdown("---")
    
    # คำทักทายจาก DJ AI
    st.markdown(f"""
    <div class="dj-speech-box">
        <span class="dj-badge">🤖 DJ AI Message</span>
        <div style="font-size: 1.1rem; line-height: 1.6; font-weight: 500;">
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
        # --- 🃏 ระบบการ์ดสลับเพลง (Song Card Switcher) ---
        
        # แถบควบคุมปุ่ม สลับเพลง ก่อนหน้า / ถัดไป
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        
        with nav_col1:
            if st.button("⬅️ เพลงก่อนหน้า", use_container_width=True):
                st.session_state.current_card_index = (st.session_state.current_card_index - 1) % total_songs
                st.rerun()

        with nav_col2:
            st.markdown(f"<h5 style='text-align: center; margin-top: 5px;'>🎵 เพลงที่ {st.session_state.current_card_index + 1} จาก {total_songs}</h5>", unsafe_allow_html=True)

        with nav_col3:
            if st.button("เพลงถัดไป ➡️", use_container_width=True):
                st.session_state.current_card_index = (st.session_state.current_card_index + 1) % total_songs
                st.rerun()

        # ดึงข้อมูลเพลงปัจจุบันที่เลือก
        current_idx = st.session_state.current_card_index
        row = songs.iloc[current_idx]
        track_name = row['track_name']
        artist_name = row['artists']
        img_url, preview_url, spot_url = get_spotify_track_info(track_name, artist_name)
        reason = data["song_reasons"].get(track_name, "เพลงนี้มีบรรยากาศและจังหวะที่เข้ากับระดับอารมณ์ของคุณได้อย่างลงตัว")

        # แสดงผลการ์ดเพลงสลับ
        st.markdown('<div class="song-card-container">', unsafe_allow_html=True)
        
        card_col1, card_col2 = st.columns([1, 1.8])
        
        with card_col1:
            if img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.markdown("<div style='height: 200px; background: #334155; border-radius: 14px; display: flex; align-items: center; justify-content: center;'>💿 No Image</div>", unsafe_allow_html=True)
                
        with card_col2:
            st.markdown(f"### {track_name}")
            st.markdown(f"🎤 **ศิลปิน:** `{artist_name}`")
            
            st.markdown(f"""
            <div class="reason-box">
                💡 <b>มุมมอง DJ:</b> {reason}
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            if preview_url:
                st.audio(preview_url, format="audio/mp3")
            if spot_url:
                st.markdown(f"[🔗 เปิดฟังเวอร์ชันเต็มบน Apple Music / Web]({spot_url})")

        st.markdown('</div>', unsafe_allow_html=True)

        # แถบ Quick Tabs ด้านล่างสำหรับการ์ดสลับ
        tab_titles = [f"เพลงที่ {i+1}" for i in range(total_songs)]
        selected_tab = st.pills("เลือกการ์ดเพลงด่วน:", tab_titles, default=f"เพลงที่ {current_idx + 1}")
        if selected_tab:
            new_idx = int(selected_tab.split()[-1]) - 1
            if new_idx != st.session_state.current_card_index:
                st.session_state.current_card_index = new_idx
                st.rerun()

    else:
        # --- 📋 มุมมองการ์ดรายการทั้งหมด (Grid View) ---
        for i, row in songs.iterrows():
            track_name = row['track_name']
            artist_name = row['artists']
            img_url, preview_url, spot_url = get_spotify_track_info(track_name, artist_name)
            reason = data["song_reasons"].get(track_name, "เพลงนี้ตรงกับระดับพลังงานและอารมณ์ที่คุณต้องการ")

            st.markdown('<div class="song-card-container">', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 3])
            
            with c1:
                if img_url:
                    st.image(img_url, width=130)
                else:
                    st.write("💿 No Image")
            with c2:
                st.subheader(f"{i+1}. {track_name}")
                st.markdown(f"🎤 **ศิลปิน:** `{artist_name}`")
                st.markdown(f"<div class='reason-box'>💡 <b>ทำไมถึงแนะนำ:</b> {reason}</div>", unsafe_allow_html=True)
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
            r=values, theta=categories, fill='toself', fillcolor='rgba(0, 242, 254, 0.3)', line_color='#00F2FE'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])), 
            showlegend=False, 
            title="📊 กราฟวิเคราะห์โทนอารมณ์ดนตรี",
            margin=dict(l=40, r=40, t=40, b=40)
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
