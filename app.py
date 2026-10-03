import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
import json
import re
from datetime import datetime

# รองรับ Speech-to-Text หากมีไลบรารี
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

# ==========================================
# 1. ตั้งค่าหน้าเว็บแบบ Fullscreen Viewport
# ==========================================
st.set_page_config(
    page_title="quietpress -- vinyl record label", 
    page_icon="💿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ซ่อน UI ดั้งเดิมของ Streamlit ทั้งหมดเพื่อให้แสดงผลแบบ Fullscreen Single Viewport
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    div[data-testid="stToolbar"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. เชื่อมต่อ API (Gemini & Secrets)
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
# 3. โหลดโมเดล Machine Learning (มี Fallback หากไม่มีไฟล์)
# ==========================================
@st.cache_resource
def load_models():
    try:
        km = joblib.load('kmeans_model.pkl')
        sc = joblib.load('scaler.pkl')
        df = pd.read_csv('spotify_clustered.csv')
        return km, sc, df
    except Exception:
        return None, None, None

kmeans, scaler, df_songs = load_models()

# ==========================================
# 4. ฟังก์ชันประมวลผลข้อมูล & ค้นหาเพลง
# ==========================================
def analyze_mood_with_gemini(text):
    """วิเคราะห์ความรู้สึกเป็นค่า Energy, Valence, Tempo"""
    if not model:
        return fallback_analyze_mood(text)
        
    prompt = f"""
    คุณคือ AI DJ นักจิตวิทยาทางดนตรี จงวิเคราะห์ข้อความต่อไปนี้แล้วแปลงเป็นค่าทางดนตรี 3 ค่า
    1. Energy (0.0 ถึง 1.0): 0 คือสงบ/อ่อนล้า, 1 คือสนุก/พลังงานสูง
    2. Valence (0.0 ถึง 1.0): 0 คือเศร้า/ลึกซึ้ง, 1 คือมีความสุข/สดใส
    3. Tempo (60.0 ถึง 200.0): ความเร็วของเพลง (BPM)

    ข้อความผู้ใช้: "{text}"
    ตอบกลับเป็นตัวเลข 3 ตัว คั่นด้วยเครื่องหมายจุลภาค (,) เท่านั้น เช่น: 0.3,0.4,75
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
    if any(word in text for word in ["เศร้า", "เหงา", "อกหัก", "ดิ่ง", "calm", "rain"]): 
        return 0.2, 0.2, 70.0
    elif any(word in text for word in ["สนุก", "มันส์", "เต้น", "สดใส"]): 
        return 0.8, 0.8, 128.0
    return 0.4, 0.5, 85.0

@st.cache_data(ttl=3600)
def get_spotify_track_info(track_name, artist_name):
    """ดึงรูปปกและตัวอย่างเสียงจาก iTunes/Deezer API"""
    clean_title = re.sub(r'[\(\[\-\~].*?[\)\]\-\~]', '', str(track_name)).strip()
    clean_artist = str(artist_name).split(',')[0].strip()
    
    try:
        query = f"{clean_title} {clean_artist}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1&entity=song"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get('resultCount', 0) > 0:
                t = data['results'][0]
                img = t.get('artworkUrl100', '').replace('100x100bb', '500x500bb')
                prev = t.get('previewUrl', None)
                if img: return img, prev
    except Exception:
        pass

    try:
        query_d = f"{clean_title} {clean_artist}"
        url_d = f"https://api.deezer.com/search?q={requests.utils.quote(query_d)}&limit=1"
        res_d = requests.get(url_d, timeout=3)
        if res_d.status_code == 200:
            data_d = res_d.json()
            if data_d.get('data') and len(data_d['data']) > 0:
                t = data_d['data'][0]
                img = t.get('album', {}).get('cover_xl') or t.get('album', {}).get('cover_big')
                prev = t.get('preview', None)
                if img: return img, prev
    except Exception:
        pass

    return "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&auto=format&fit=crop&q=80", "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"

# ==========================================
# 5. จัดการ Session State
# ==========================================
if 'cart_count' not in st.session_state:
    st.session_state.cart_count = 0
if 'current_track_idx' not in st.session_state:
    st.session_state.current_track_idx = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'is_liked' not in st.session_state:
    st.session_state.is_liked = False
if 'active_playlist' not in st.session_state:
    # เพลย์ลิสต์เริ่มต้นของ quietpress
    st.session_state.active_playlist = [
        {
            "title": "Fern Light",
            "artist": "Helia Marsh",
            "tag": "🍃 #VernalWoods",
            "reason": "จังหวะ Drone นุ่มนวลผสมเสียงธรรมชาติ บันทึกสดบนแผ่น LPs Cut ครั้งเดียว",
            "img": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&auto=format&fit=crop&q=80",
            "preview": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"
        },
        {
            "title": "Silent Moss",
            "artist": "Vernal Echoes",
            "tag": "🌙 #CalmListener",
            "reason": "โทนเสียงอะคูสติกโอบกอดความรู้สึกอย่างสงบ เหมาะสำหรับค่ำคืนที่ต้องการความผ่อนคลาย",
            "img": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=400&auto=format&fit=crop&q=80",
            "preview": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3"
        }
    ]

# ==========================================
# 6. รับ Query Parameter สั่งเปลี่ยนเพลง/สั่งซื้อ
# ==========================================
query_params = st.query_params
if "action" in query_params:
    action = query_params["action"]
    if action == "add_cart":
        st.session_state.cart_count += 1
    elif action == "toggle_play":
        st.session_state.is_playing = not st.session_state.is_playing
    elif action == "next":
        st.session_state.current_track_idx = (st.session_state.current_track_idx + 1) % len(st.session_state.active_playlist)
    elif action == "prev":
        st.session_state.current_track_idx = (st.session_state.current_track_idx - 1 + len(st.session_state.active_playlist)) % len(st.session_state.active_playlist)
    elif action == "toggle_like":
        st.session_state.is_liked = not st.session_state.is_liked
    st.query_params.clear()

curr_track = st.session_state.active_playlist[st.session_state.current_track_idx]

# ==========================================
# 7. Render หน้าเว็บด้วย HTML5/CSS/JS Component
# ==========================================
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="https://db.onlinewebfonts.com/c/a64ff11d2c24584c767f6257e880dc65?family=Helvetica+Regular">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    html, body {{
      font-family: 'Helvetica Regular', Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      height: 100vh;
      overflow: hidden;
      background-color: #000;
      color: #fff;
    }}

    /* Liquid Glass Effect */
    .liquid-glass {{
      background: rgba(255, 255, 255, 0.01);
      background-blend-mode: luminosity;
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      border: none;
      box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);
      position: relative;
      overflow: hidden;
    }}
    .liquid-glass::before {{
      content: '';
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1.4px;
      background: linear-gradient(180deg,
        rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 20%,
        rgba(255,255,255,0) 40%, rgba(255,255,255,0) 60%,
        rgba(255,255,255,0.15) 80%, rgba(255,255,255,0.45) 100%);
      -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
    }}

    /* Fade-up animations */
    @keyframes fade-up {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to   {{ opacity: 1; transform: none; }}
    }}
    .animate-fade-up {{
      animation: fade-up 0.7s cubic-bezier(0.22, 1, 0.36, 1) backwards;
    }}
    .delay-1 {{ animation-delay: 0.1s; }}
    .delay-2 {{ animation-delay: 0.25s; }}
    .delay-3 {{ animation-delay: 0.4s; }}
    .delay-4 {{ animation-delay: 0.55s; }}
    .delay-5 {{ animation-delay: 0.75s; }}

    /* แผ่นเสียงหมุน 3D */
    @keyframes rotateVinyl {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
    .animate-vinyl-spin {{
      animation: rotateVinyl 6s linear infinite;
    }}
    .animate-vinyl-pause {{
      animation-play-state: paused;
    }}

    /* Equalizer Bars */
    @keyframes equalBlink {{
      0%, 100% {{ height: 3px; }}
      50% {{ height: 14px; }}
    }}
    .eq-bar {{
      width: 3px;
      margin: 0 1px;
      background: #1d4ed8;
      border-radius: 2px;
      animation: equalBlink 1s ease-in-out infinite alternate;
    }}
    .eq-bar:nth-child(1) {{ animation-delay: 0.1s; }}
    .eq-bar:nth-child(2) {{ animation-delay: 0.4s; }}
    .eq-bar:nth-child(3) {{ animation-delay: 0.2s; }}
    .eq-bar:nth-child(4) {{ animation-delay: 0.5s; }}
  </style>
</head>
<body>
  <div class="relative h-screen w-full overflow-hidden select-none">
    
    <!-- Boomerang Video Canvas Background -->
    <div class="absolute inset-0 z-0 scale-[1.08] origin-center overflow-hidden pointer-events-none">
      <video id="bgVideo" src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260611_183632_c311af08-e4b7-458f-81e7-79847a49b3d3.mp4" autoplay muted playsinline crossorigin="anonymous" class="w-full h-full object-cover"></video>
      <canvas id="bgCanvas" class="w-full h-full object-cover hidden"></canvas>
    </div>

    <!-- Header (absolute, top, z-20) -->
    <header class="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-4 sm:px-8 py-5">
      <div class="flex items-center gap-2.5">
        <svg class="w-5 h-5 fill-white" viewBox="0 0 256 256">
          <path d="M 256 256 L 128 256 C 198.692 256 256 198.692 256 128 C 256 57.308 198.692 0 128 0 C 57.308 0 0 57.308 0 128 C 0 198.692 57.308 256 128 256 L 0 256 L 0 0 L 256 0 Z M 128 104 C 141.255 104 152 114.745 152 128 C 152 141.255 141.255 152 128 152 C 114.745 152 104 141.255 104 128 C 104 114.745 114.745 104 128 104 Z" />
        </svg>
        <span class="text-base tracking-tight text-white font-medium">quietpress</span>
      </div>

      <nav class="hidden md:flex items-center gap-8 text-sm text-white/90">
        <a href="#" class="hover:text-white transition-colors">Anthology</a>
        <a href="#" class="hover:text-white transition-colors">Talents</a>
        <a href="#" class="hover:text-white transition-colors">Sound diary</a>
        <a href="#" class="hover:text-white transition-colors">Playback salon</a>
      </nav>

      <div class="flex items-center gap-3">
        <a href="?action=add_cart" target="_self" class="rounded-xl bg-white p-1 pr-3 sm:pr-4 flex items-center gap-2.5 text-gray-900 transition-transform hover:scale-105 active:scale-95 shadow-md">
          <div class="h-7 w-7 rounded-lg bg-blue-700 flex items-center justify-center text-white">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
          </div>
          <span class="text-xs sm:text-sm font-medium"><span class="hidden sm:inline">Cart </span>({st.session_state.cart_count})</span>
        </a>
      </div>
    </header>

    <!-- Hero Content (centered, z-10) -->
    <main className="relative z-10 h-full flex flex-col justify-center px-4 sm:px-6 pt-24 max-w-5xl mx-auto" style="padding-top: 11rem; padding-left: 2rem;">
      <div class="animate-fade-up delay-1 mb-5">
        <span class="liquid-glass rounded-lg px-4 py-1.5 text-xs sm:text-sm text-white" style="background: rgba(255, 255, 255, 0.16);">
          Press 04 . Vernal woods
        </span>
      </div>

      <h1 class="animate-fade-up delay-2 max-w-3xl text-4xl sm:text-5xl md:text-6xl lg:text-7xl leading-[1.1] text-white">
        records cut for the<br>calm listener.
      </h1>

      <p class="animate-fade-up delay-3 mt-5 max-w-md text-sm sm:text-base md:text-lg leading-relaxed text-white/90">
        Drone, roots, and nature-captured sound on wax LPs. Every disc cut just once, snag it or miss.
      </p>

      <div class="animate-fade-up delay-4 mt-8 flex flex-col sm:flex-row gap-3">
        <a href="?action=add_cart" target="_self" class="rounded-xl bg-white px-7 py-2.5 text-sm text-gray-900 hover:scale-105 active:scale-95 transition-transform text-center font-medium">
          Browse the shelves
        </a>
        <a href="?action=toggle_play" target="_self" class="liquid-glass rounded-xl px-7 py-2.5 text-sm text-white hover:scale-105 active:scale-95 transition-transform text-center font-medium">
          Newest arrivals
        </a>
      </div>
    </main>

    <!-- Now Playing Widget (bottom-right, z-20) -->
    <div class="absolute bottom-4 right-4 sm:bottom-6 sm:right-6 md:bottom-8 md:right-10 z-20 w-[270px] sm:w-72 animate-fade-up delay-5 flex flex-col gap-2">
      
      <!-- DJ Reason Box สไตล์ app.py -->
      <div class="liquid-glass rounded-2xl p-2.5 text-xs text-white/90 shadow-xl border border-white/10">
        <div class="flex items-center justify-between mb-1">
          <span class="text-[10px] font-bold uppercase tracking-wider text-blue-300">🤖 DJ AI Perspective</span>
          {'<div class="flex items-end h-3"><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span></div>' if st.session_state.is_playing else ''}
        </div>
        <p class="line-clamp-2 leading-tight text-white/80">{curr_track['reason']}</p>
      </div>

      <!-- Track Card -->
      <div class="rounded-2xl bg-white p-2.5 pr-4 shadow-lg text-gray-900">
        <div class="flex items-center gap-3">
          <div class="relative w-11 h-11 flex-shrink-0 flex items-center justify-center">
            <!-- 3D Vinyl Disk -->
            <div class="absolute right-[-5px] w-10 h-10 rounded-full bg-neutral-900 border border-neutral-700 flex items-center justify-center shadow-md animate-vinyl-spin {'animate-vinyl-pause' if not st.session_state.is_playing else ''}">
              <div class="w-3 h-3 rounded-full bg-blue-700"></div>
            </div>
            <!-- Album Cover -->
            <img src="{curr_track['img']}" class="relative z-10 w-11 h-11 rounded-xl object-cover shadow-md" />
          </div>

          <div class="flex-1 min-w-0">
            <span class="text-[9px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded truncate inline-block mb-0.5">{curr_track['tag']}</span>
            <p class="text-sm font-medium truncate text-gray-900 leading-none">{curr_track['artist']} -- {curr_track['title']}</p>
            <div class="mt-2 flex items-center gap-2">
              <div class="h-1 flex-1 rounded-full bg-gray-200 overflow-hidden">
                <div class="h-full bg-blue-700 {'w-[65%]' if st.session_state.is_playing else 'w-[30%]'}" ></div>
              </div>
              <div class="flex text-[10px] text-gray-500 font-mono gap-1">
                <span>0:33</span><span>-1:21</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Controls Row -->
      <div class="flex items-center gap-2">
        <a href="?action=prev" target="_self" class="flex-1 rounded-2xl bg-white py-2 text-center text-sm font-bold text-gray-900 shadow-lg hover:scale-105 active:scale-95 transition-transform">Prev</a>
        <a href="?action=toggle_like" target="_self" class="h-10 w-10 rounded-full bg-white shadow-lg flex items-center justify-center hover:scale-110 active:scale-95 transition-transform">
          <svg class="w-4 h-4 {'text-blue-700 fill-blue-700' if st.session_state.is_liked else 'text-blue-700'}" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.684a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>
        </a>
        <a href="?action=next" target="_self" class="flex-1 rounded-2xl bg-white py-2 text-center text-sm font-bold text-gray-900 shadow-lg hover:scale-105 active:scale-95 transition-transform">Next</a>
      </div>

    </div>
  </div>

  <!-- Audio Player Elements -->
  <audio id="audioPlayer" src="{curr_track['preview']}" {'autoplay' if st.session_state.is_playing else ''}></audio>

  <script>
    // Boomerang Video Loop Logic
    const video = document.getElementById('bgVideo');
    const canvas = document.getElementById('bgCanvas');
    const ctx = canvas.getContext('2d');
    let frames = [];

    video.addEventListener('ended', () => {{
      video.classList.add('hidden');
      canvas.classList.remove('hidden');
      
      let frameIdx = 0;
      let forward = true;
      setInterval(() => {{
        if (frames.length > 0) {{
          ctx.putImageData(frames[frameIdx], 0, 0);
          if (forward) {{
            frameIdx++;
            if (frameIdx >= frames.length) {{ frameIdx = frames.length - 1; forward = false; }}
          }} else {{
            frameIdx--;
            if (frameIdx < 0) {{ frameIdx = 0; forward = true; }}
          }}
        }}
      }}, 1000 / 30);
    }});

    function capture() {{
      if (!video.paused && !video.ended) {{
        if (canvas.width === 0 && video.videoWidth > 0) {{
          const scale = Math.min(1, 960 / video.videoWidth);
          canvas.width = video.videoWidth * scale;
          canvas.height = video.videoHeight * scale;
        }}
        if (canvas.width > 0) {{
          const offCanvas = document.createElement('canvas');
          offCanvas.width = canvas.width;
          offCanvas.height = canvas.height;
          const offCtx = offCanvas.getContext('2d');
          offCtx.drawImage(video, 0, 0, canvas.width, canvas.height);
          frames.push(offCtx.getImageData(0, 0, canvas.width, canvas.height));
        }}
        requestAnimationFrame(capture);
      }}
    }}
    video.addEventListener('play', () => requestAnimationFrame(capture));
  </script>
</body>
</html>
"""

st.components.v1.html(html_content, height=800, scrolling=False)

# ==========================================
# 8. ส่วนค้นหาเพลงตามอารมณ์สไตล์ AI DJ (Bottom Controls)
# ==========================================
with st.expander("🎙️ พิมพ์/พูดความรู้สึกเพื่อแมตช์เพลงด้วย AI DJ"):
    user_mood = st.text_input("ระบุอารมณ์ของคุณที่นี่:", placeholder="เช่น เหนื่อยจากงาน อยากฟังเพลงสไตล์ Drone ผ่อนคลาย...")
    if st.button("✨ ให้ AI จัดเพลงให้ทันที", type="primary"):
        if user_mood:
            with st.spinner("🎧 AI DJ กำลังวิเคราะห์อารมณ์ดนตรี..."):
                e, v, t = analyze_mood_with_gemini(user_mood)
                
                # หากมีโมเดล KMeans ให้ทำ Clustered Match
                if kmeans and scaler and df_songs is not None:
                    try:
                        scaled = scaler.transform([[0.5, e, v, t]])
                        cluster = kmeans.predict(scaled)[0]
                        matched_df = df_songs[df_songs['cluster_id'] == cluster].sample(min(3, len(df_songs)))
                        
                        new_playlist = []
                        for _, r in matched_df.iterrows():
                            t_name = r.get('track_name', 'Track')
                            a_name = r.get('artists', 'Artist')
                            img, prev = get_spotify_track_info(t_name, a_name)
                            new_playlist.append({
                                "title": t_name,
                                "artist": a_name,
                                "tag": f"✨ #{user_mood[:10]}",
                                "reason": f"เพลงนี้ตรงกับค่าอารมณ์ของคุณ (Energy: {e:.2f}, Tempo: {int(t)} BPM)",
                                "img": img,
                                "preview": prev
                            })
                        st.session_state.active_playlist = new_playlist
                        st.session_state.current_track_idx = 0
                        st.session_state.is_playing = True
                        st.rerun()
                    except Exception:
                        pass
                else:
                    st.success(f"วิเคราะห์อารมณ์สำเร็จ! (Energy: {e:.2f}, Valence: {v:.2f}, Tempo: {int(t)} BPM)")
