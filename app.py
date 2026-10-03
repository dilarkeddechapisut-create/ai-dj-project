import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
import json
from datetime import datetime
from streamlit_mic_recorder import speech_to_text
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# ==========================================
# 1. ตั้งค่าหน้าเว็บ
# ==========================================
st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")
st.markdown("พิมพ์บอกความรู้สึก หรือ **กดไมค์เพื่อพูด** เลือกจำนวนเพลง แล้วให้ AI DJ จัดเพลงและส่งเข้า Spotify ได้ทันที!")

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ API (Gemini & Google Sheets)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-3.6-flash')
    else:
        model = None
except Exception as e:
    model = None

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
# 4. ฟังก์ชันเบื้องหลัง (Gemini + Spotify API)
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
        clean_text = response.text.replace('`', '').strip()
        values = clean_text.split(',')
        return float(values[0].strip()), float(values[1].strip()), float(values[2].strip())
    except Exception:
        return fallback_analyze_mood(text)

def fallback_analyze_mood(text):
    """ระบบสำรองหาก Gemini ขัดข้อง"""
    text = text.lower()
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง"]): return 0.2, 0.2, 80.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น"]): return 0.8, 0.8, 130.0
    return 0.5, 0.5, 100.0

@st.cache_data(ttl=3600)
def get_spotify_track_info(track_name, artist_name):
    """ดึงรูปปก, ตัวอย่างเพลง (Audio Preview), และลิงก์ฟังเพลง"""
    try:
        query = f"{track_name} {artist_name}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1&entity=song"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('resultCount', 0) > 0:
                track = data['results'][0]
                img_url = track.get('artworkUrl100', '').replace('100x100bb', '300x300bb')
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

# --- ระบบ OAuth สำหรับ Spotify Playlist ---
def get_spotify_oauth():
    client_id = st.secrets.get("SPOTIPY_CLIENT_ID", "")
    client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET", "")
    redirect_uri = st.secrets.get("SPOTIPY_REDIRECT_URI", "")
    
    if not (client_id and client_secret and redirect_uri):
        return None
        
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-modify-public playlist-modify-private",
        show_dialog=True
    )

def create_spotify_playlist_on_user_account(token_info, playlist_name, songs_df):
    """สร้าง Playlist และเพิ่มเพลงลงในบัญชี Spotify ของผู้ใช้"""
    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_id = sp.current_user()["id"]
        
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=True,
            description="จัดทำโดย AI DJ Mood Matcher"
        )
        
        track_uris = []
        for _, row in songs_df.iterrows():
            q = f"track:{row['track_name']} artist:{row['artists']}"
            res = sp.search(q=q, type="track", limit=1)
            tracks = res.get('tracks', {}).get('items', [])
            if tracks:
                track_uris.append(tracks[0]['uri'])
            else:
                q_fb = f"{row['track_name']} {row['artists']}"
                res_fb = sp.search(q=q_fb, type="track", limit=1)
                tracks_fb = res_fb.get('tracks', {}).get('items', [])
                if tracks_fb:
                    track_uris.append(tracks_fb[0]['uri'])

        if track_uris:
            sp.playlist_add_items(playlist_id=playlist['id'], items=track_uris)
            return playlist['external_urls']['spotify'], len(track_uris)
        return None, 0
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการสร้าง Playlist: {e}")
        return None, 0

# ==========================================
# 5. ระบบความจำ (Session State & Spotify Auth)
# ==========================================
if 'playlist_data' not in st.session_state:
    st.session_state.playlist_data = None
if 'feedback_submitted' not in st.session_state:
    st.session_state.feedback_submitted = False
if 'spotify_token' not in st.session_state:
    st.session_state.spotify_token = None

sp_oauth = get_spotify_oauth()
if sp_oauth and "code" in st.query_params:
    try:
        code = st.query_params["code"]
        token_info = sp_oauth.get_access_token(code)
        st.session_state.spotify_token = token_info
        st.query_params.clear()
        st.success("🟢 เชื่อมต่อ Spotify เรียบร้อยแล้ว!")
    except Exception as e:
        st.error(f"ไม่สามารถรับ Token จาก Spotify ได้: {e}")

# ==========================================
# 6. ส่วน UI หน้าเว็บ (ไมโครโฟน + กล่องข้อความ)
# ==========================================
st.markdown("### 🗣️ เล่าความรู้สึกของคุณ")

text_from_mic = speech_to_text(
    language='th-TH', 
    start_prompt="🎙️ กดเพื่อพูด (พูดเสร็จให้กดซ้ำอีกรอบ)", 
    stop_prompt="🛑 กำลังฟัง... (กดเพื่อหยุด)", 
    just_once=False,
    key='STT'
)

default_text = text_from_mic if text_from_mic else ""
mood_text = st.text_area("หรือพิมพ์ความรู้สึกที่นี่:", value=default_text, placeholder="เช่น วันนี้ฝนตก เหงาจังเลย...")

num_songs = st.slider("🎵 เลือกจำนวนเพลงที่ต้องการใน Playlist:", min_value=5, max_value=15, value=5, step=1)

if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", width="stretch"):
    if not mood_text:
        st.warning("กรุณาพิมพ์หรือพูดความรู้สึกของคุณก่อนครับ")
    else:
        with st.spinner("DJ (Gemini) กำลังตีความความรู้สึกและวิเคราะห์รายเพลง..."):
            t_energy, t_valence, t_tempo = analyze_mood_with_gemini(mood_text)
            
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            scaled_input = scaler.transform(user_features)
            predicted_cluster = kmeans.predict(scaled_input)[0]
            
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(num_songs, len(cluster_songs)))
            
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
                  "dj_text": "ข้อความทักทายภาพรวมสั้นๆ ภาษาไทย เป็นกันเอง",
                  "reasons": {{
                    "ชื่อเพลงเป๊ะๆ ตามลิสต์": "เหตุผลสั้นๆ 1-2 ประโยคภาษาไทย ว่าทำไมเพลงนี้ถึงเข้ากับอารมณ์นี้และเพลงเป็นสไตล์ไหน"
                  }}
                }}
                """
                
                try:
                    response = model.generate_content(
                        prompt_dj,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    dj_data = json.loads(response.text)
                    dj_response = dj_data.get("dj_text", dj_response)
                    song_reasons = dj_data.get("reasons", {})
                except Exception as e:
                    dj_response = "(ระบบ Gemini ขัดข้องชั่วคราว) แต่นี่คือเพลงที่เราจัดไว้ให้ครับ!"

            st.session_state.playlist_data = {
                "mood": mood_text,
                "cluster": predicted_cluster,
                "dj_text": dj_response,
                "song_reasons": song_reasons,
                "sampled_songs": sampled_songs,
                "features": {"energy": t_energy, "valence": t_valence, "tempo": t_tempo}
            }
            st.session_state.feedback_submitted = False

# ==========================================
# 7. ส่วนแสดงผลลัพธ์
# ==========================================
if st.session_state.playlist_data:
    data = st.session_state.playlist_data
    
    st.success(f"จัดเพลงเสร็จเรียบร้อย! ได้รับทั้งหมด {len(data['sampled_songs'])} เพลง")
    st.markdown("### 💬 ข้อความจาก DJ AI (Powered by Google Gemini)")
    st.info(data["dj_text"])

    st.markdown("---")
    st.markdown("### 🟢 สร้าง Playlist นี้บน Spotify ของคุณ")
    
    if not sp_oauth:
        st.warning("⚠️ ยังไม่ได้ตั้งค่า SPOTIPY Credentials ใน Streamlit Secrets")
    else:
        if not st.session_state.spotify_token:
            auth_url = sp_oauth.get_authorize_url()
            st.markdown(f"[👉 คลิกที่นี่เพื่อล็อกอิน Spotify และอนุญาตการสร้าง Playlist]({auth_url})")
        else:
            playlist_name_input = st.text_input("ชื่อ Playlist บน Spotify:", value=f"AI DJ Mood: {data['mood'][:20]}")
            if st.button("➕ บันทึก Playlist ลง Spotify ทันที", type="primary"):
                with st.spinner("กำลังสร้าง Playlist และเพิ่มเพลงเข้าสู่ Spotify ของคุณ..."):
                    sp_url, added_count = create_spotify_playlist_on_user_account(
                        st.session_state.spotify_token,
                        playlist_name_input,
                        data["sampled_songs"]
                    )
                    if sp_url:
                        st.balloons()
                        st.success(f"🎉 สร้าง Playlist สำเร็จ! เพิ่มเพลงสำเร็จ {added_count} เพลง")
                        st.markdown(f"👉 [🎧 คลิกที่นี่เพื่อเปิดฟัง Playlist บน Spotify ของคุณ]({sp_url})")

    st.markdown("---")
    st.markdown(f"### 🎼 รายชื่อเพลงแนะนำ (กลุ่มดนตรีที่ {data['cluster']})")

    for _, row in data["sampled_songs"].iterrows():
        track_name = row['track_name']
        artist_name = row['artists']
        
        img_url, preview_url, spot_url = get_spotify_track_info(track_name, artist_name)
        
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if img_url:
                st.image(img_url, width=120)
            else:
                st.write("💿 No Image")
                
        with col2:
            st.subheader(track_name)
            st.write(f"🎤 **ศิลปิน:** {artist_name}")
            
            reason = data["song_reasons"].get(track_name, None)
            if reason:
                st.caption(f"💡 **ทำไม DJ ถึงเลือกเพลงนี้:** {reason}")
            
            if spot_url:
                st.markdown(f"[🎧 ฟังเพลงเต็มคลิกที่นี่]({spot_url})")
            if preview_url:
                st.audio(preview_url, format="audio/mp3")
                
        st.divider()

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
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.markdown("### 📝 คุณชอบ Playlist นี้ไหม?")
    
    if not st.session_state.feedback_submitted:
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("👍 โดนใจสุดๆ", width="stretch"):
                save_feedback(data["mood"], data["cluster"], "Like")
                st.session_state.feedback_submitted = True
                st.rerun()
        with col2:
            if st.button("👎 ไม่ค่อยเข้ากัน", width="stretch"):
                save_feedback(data["mood"], data["cluster"], "Dislike")
                st.session_state.feedback_submitted = True
                st.rerun()
    else:
        st.success("💖 ขอบคุณสำหรับเสียงตอบรับครับ! ข้อมูลถูกบันทึกลงฐานข้อมูลเรียบร้อยแล้ว")
