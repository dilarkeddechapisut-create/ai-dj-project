import streamlit as st
import pandas as pd
import joblib
import os
import google.generativeai as genai

st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧")
st.title("🎧 AI DJ: จัด Playlist ตามอารมณ์")
st.markdown("พิมพ์บอกความรู้สึกของคุณ แล้วให้ AI DJ จัดเพลงให้เลย!")

# 1. ตั้งค่า Google Gemini API (ดึงจาก Streamlit Secrets)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    # ใช้ gemini-1.5-flash เพราะทำงานรวดเร็วและเหมาะกับข้อความ
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("🚨 ไม่พบ API Key! กรุณาตั้งค่า GOOGLE_API_KEY ใน Streamlit Secrets")
    st.stop()

# 2. โหลดโมเดล K-Means
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

# 3. ระบบวิเคราะห์อารมณ์เป็นตัวเลข
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

# 4. ฟังก์ชันส่ง Prompt ให้ Google Gemini
def generate_dj_message_gemini(mood, songs):
    prompt = f"""
    คุณคือ 'DJ AI' สุดคูลและเข้าอกเข้าใจคนฟัง
    ผู้ใช้บอกความรู้สึกว่า: "{mood}"
    และนี่คือเพลง 5 เพลงที่ระบบคัดเลือกมาให้:
    {songs}
    
    จงเขียนข้อความสั้นๆ ทักทายผู้ใช้ แนะนำ Playlist นี้ว่าทำไมถึงเหมาะกับอารมณ์ของเขา ใช้ภาษาไทย เป็นกันเอง
    ห้ามแต่งชื่อเพลงขึ้นมาเองเด็ดขาด ให้กล่าวถึงเพลงจากลิสต์ที่ให้ไปเท่านั้น
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"(DJ ขัดข้องชั่วคราว) แต่นี่คือเพลงที่เราจัดไว้ให้ครับ! Error: {e}"

# 5. UI หน้าเว็บ
mood_text = st.text_area("วันนี้คุณรู้สึกอย่างไร?", placeholder="เช่น วันนี้ฝนตก เหงาจังเลย อยากได้เพลงฮีลใจ")

if st.button("🎵 จัด Playlist ให้หน่อย", type="primary", use_container_width=True):
    if not mood_text:
        st.warning("กรุณาพิมพ์ความรู้สึกของคุณก่อนครับ")
    else:
        with st.spinner("DJ (Gemini) กำลังวิเคราะห์อารมณ์และแต่งข้อความ..."):
            # ก. จัดกลุ่มเพลงด้วย K-Means
            t_energy, t_valence, t_tempo = analyze_mood_to_features(mood_text)
            user_features = [[0.5, t_energy, t_valence, t_tempo]]
            scaled_input = scaler.transform(user_features)
            predicted_cluster = kmeans.predict(scaled_input)[0]
            
            cluster_songs = df_songs[df_songs['cluster_id'] == predicted_cluster]
            sampled_songs = cluster_songs.sample(min(5, len(cluster_songs)))
            
            song_list_str = "\n".join([
                f"- {row['track_name']} (ศิลปิน: {row['artists']})" 
                for _, row in sampled_songs.iterrows()
            ])
            
            # ข. ให้ Gemini แต่งคำพูด
            dj_response = generate_dj_message_gemini(mood_text, song_list_str)
            
            # ค. แสดงผล
            st.success("จัดเพลงเสร็จเรียบร้อย!")
            st.markdown("### 💬 ข้อความจาก DJ AI (Powered by Google Gemini)")
            st.info(dj_response)
            
            st.markdown(f"### 🎼 รายชื่อเพลง (กลุ่มดนตรีที่ {predicted_cluster})")
            st.text(song_list_str)