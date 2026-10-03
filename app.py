import streamlit as st
import pandas as pd
import joblib
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧", layout="centered")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")

# 1. โหลดค่า Secrets และตั้งค่า APIs
try:
    # ตั้งค่า Gemini
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    # ตั้งค่า Spotify
    sp_client_id = st.secrets["SPOTIPY_CLIENT_ID"]
    sp_client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=sp_client_id, 
        client_secret=sp_client_secret
    ))
except Exception as e:
    st.error("🚨 กรุณาตั้งค่า API Keys (Google และ Spotify) ใน Streamlit Secrets ก่อน")
    st.stop()

# 2. โหลดโมเดล (ฟังก์ชันเดิม)
@st.cache_resource
def load_models():
    return joblib.load('kmeans_model.pkl'), joblib.load('scaler.pkl'), pd.read_csv('spotify_clustered.csv')
kmeans, scaler, df_songs = load_models()

# 3. วิเคราะห์อารมณ์ (ฟังก์ชันเดิม)
def analyze_mood_to_features(text):
    text = text.lower()
    energy, valence, tempo = 0.5, 0.5, 100.0 
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก"]): return 0.2, 0.2, 80.0
    if any(word in text for word in ["สนุก", "มันส์", "เต้น"]): return 0.8, 0.8, 130.0
    if any(word in text for word in ["ชิล", "สบาย", "ทำงาน"]): return 0.4, 0.6, 90.0
    if any(word in text for word in ["โกรธ", "โมโห", "ร็อค"]): return 0.9, 0.3, 140.0
    return energy, valence, tempo

# 4. ฟังก์ชันค้นหาเพลงใน Spotify เพื่อดึงรูปปก 🌟 (ส่วนที่เพิ่มมาใหม่)
def get_spotify_track_info(track_name, artist_name):
    # ค้นหาโดยใช้ชื่อเพลงและชื่อศิลปิน
    query = f"track:{track_name} artist:{artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    
    if results['tracks']['items']:
        track_data = results['tracks']['items'][0]
        # ดึงรูปปกอัลบั้ม (เอาภาพขนาดกลาง index 1)
        image_url = track_data['album']['images'][1]['url'] if track_data['album']['images'] else None
        # ดึงเสียงตัวอย่าง 30 วิ (บางเพลงอาจจะไม่มี)
        preview_url = track_data['preview_url'] 
        # ลิงก์ไปฟังเต็มๆ
        spotify_url = track_data['external_urls']['spotify']
        return image_url, preview_url, spotify_url
    return None, None, None

# 5. UI หน้าเว็บ
mood_text = st.text_area("วันนี้คุณรู้สึกอย่างไร?", placeholder="เช่น เหงาจังเลย อยากฟังเพลงเศร้า")

if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", use_container_width=True):
    if not mood_text:
        st.warning("กรุณาพิมพ์ความรู้สึกของคุณก่อนครับ")
    else:
        with st.spinner("DJ กำลังจัดเพลงและดึงรูปปกจาก Spotify..."):
            # จัดกลุ่มและสุ่มเพลง
            t_energy, t_valence, t_tempo = analyze_mood_to_features(mood_text)
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            predicted_cluster = kmeans.predict(scaler.transform(user_features))[0]
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(5, len(cluster_songs)))
            
            # ให้ Gemini แต่งคำพูด
            song_names = ", ".join(sampled_songs['track_name'].tolist())
            prompt = f"คุณคือ DJ AI ผู้ใช้บ่นว่า '{mood_text}' ให้แนะนำเพลงเหล่านี้สั้นๆ เป็นภาษาไทย: {song_names}"
            dj_response = model.generate_content(prompt).text
            
            st.success("จัดเพลงเสร็จเรียบร้อย!")
            st.info(f"💬 **DJ AI:** {dj_response}")
            
            st.markdown("### 🎼 เพลย์ลิสต์ของคุณ")
            
            # วนลูปแสดงเพลงทีละบรรทัด พร้อมรูปปก 🌟
            for _, row in sampled_songs.iterrows():
                # ดึงข้อมูลจาก Spotify
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
                        st.markdown(f"[🎧 ฟังเต็มๆ บน Spotify]({spot_url})")
                    if preview_url:
                        st.audio(preview_url, format="audio/mp3")
                        
                st.divider() # เส้นคั่นแต่ละเพลง