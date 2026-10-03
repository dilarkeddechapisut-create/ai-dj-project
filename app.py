import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
import json
import re
from datetime import datetime

# รองรับ Speech-to-Text สตรีมไลน์
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

# ==========================================
# 1. Page Config & CSS Injection
# ==========================================
st.set_page_config(
    page_title="quietpress -- vinyl record label",
    page_icon="💿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Glassmorphism, Helvetica, Vinyl Rotation & Boomerang Background CSS
st.markdown("""
<link rel="stylesheet" href="https://db.onlinewebfonts.com/c/a64ff11d2c24584c767f6257e880dc65?family=Helvetica+Regular">

<style>
    /* Reset & Fullscreen Viewport */
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    div[data-testid="stToolbar"] {display: none;}
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Helvetica Regular', Helvetica, Arial, sans-serif !important;
        background-color: #050505;
        color: #ffffff;
        overflow-x: hidden;
    }

    /* Background Video Container */
    .bg-video-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 0;
        overflow: hidden;
        pointer-events: none;
        transform: scale(1.08);
        transform-origin: center;
    }
    .bg-video-container video, .bg-video-container canvas {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    /* Liquid Glass CSS Class */
    .liquid-glass {
        background: rgba(255, 255, 255, 0.03);
        background-blend-mode: luminosity;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.2), 0 10px 30px rgba(0, 0, 0, 0.5);
        border-radius: 16px;
    }

    /* Animations */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-fade-up {
        animation: fadeUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) backwards;
    }

    @keyframes rotateVinyl {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .vinyl-spin {
        animation: rotateVinyl 6s linear infinite;
    }
    .vinyl-pause {
        animation-play-state: paused;
    }

    @keyframes equalBlink {
        0%, 100% { height: 3px; }
        50% { height: 14px; }
    }
    .eq-bar {
        width: 3px;
        margin: 0 1px;
        background: #1d4ed8;
        border-radius: 2px;
        animation: equalBlink 1s ease-in-out infinite alternate;
    }
    .eq-bar:nth-child(1) { animation-delay: 0.1s; }
    .eq-bar:nth-child(2) { animation-delay: 0.4s; }
    .eq-bar:nth-child(3) { animation-delay: 0.2s; }
    .eq-bar:nth-child(4) { animation-delay: 0.5s; }

    /* Custom Streamlit Input/Button Overrides for Glass Look */
    .stTextInput input {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 12px !important;
        backdrop-filter: blur(8px);
    }
    .stButton button {
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
</style>

<!-- Background Boomerang Video Overlay -->
<div class="bg-video-container">
    <video id="bgVid" autoplay muted playsinline crossorigin="anonymous">
        <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260611_183632_c311af08-e4b7-458f-81e7-79847a49b3d3.mp4" type="video/mp4">
    </video>
    <canvas id="bgCanv" style="display:none;"></canvas>
</div>

<script>
    // Ping-Pong Boomerang Loop Handler
    const vid = document.getElementById('bgVid');
    const canv = document.getElementById('bgCanv');
    if (vid && canv) {
        const ctx = canv.getContext('2d');
        let frames = [];
        vid.addEventListener('ended', () => {
            vid.style.display = 'none';
            canv.style.display = 'block';
            let idx = 0, fwd = true;
            setInterval(() => {
                if (frames.length > 0) {
                    ctx.putImageData(frames[idx], 0, 0);
                    idx = fwd ? idx + 1 : idx - 1;
                    if (idx >= frames.length - 1) fwd = false;
                    if (idx <= 0) fwd = true;
                }
            }, 1000 / 30);
        });
        function grab() {
            if (!vid.paused && !vid.ended) {
                if (canv.width === 0 && vid.videoWidth > 0) {
                    const sc = Math.min(1, 960 / vid.videoWidth);
                    canv.width = vid.videoWidth * sc;
                    canv.height = vid.videoHeight * sc;
                }
                if (canv.width > 0) {
                    const oc = document.createElement('canvas');
                    oc.width = canv.width; oc.height = canv.height;
                    oc.getContext('2d').drawImage(vid, 0, 0, canv.width, canv.height);
                    frames.push(oc.getContext('2d').getImageData(0, 0, canv.width, canv.height));
                }
                requestAnimationFrame(grab);
            }
        }
        vid.addEventListener('play', () => requestAnimationFrame(grab));
    }
</script>
""", unsafe_allow_html=True)

# ==========================================
# 2. Gemini API & ML Model Initialization
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

@st.cache_resource
def load_ml_models():
    try:
        km = joblib.load('kmeans_model.pkl')
        sc = joblib.load('scaler.pkl')
        df = pd.read_csv('spotify_clustered.csv')
        return km, sc, df
    except Exception:
        return None, None, None

kmeans, scaler, df_songs = load_ml_models()

@st.cache_data(ttl=3600)
def fetch_track_metadata(track_name, artist_name):
    clean_t = re.sub(r'[\(\[\-\~].*?[\)\]\-\~]', '', str(track_name)).strip()
    clean_a = str(artist_name).split(',')[0].strip()
    try:
        q = f"{clean_t} {clean_a}"
        res = requests.get(f"https://itunes.apple.com/search?term={requests.utils.quote(q)}&limit=1&entity=song", timeout=3)
        if res.status_code == 200 and res.json().get('resultCount', 0) > 0:
            item = res.json()['results'][0]
            return item.get('artworkUrl100', '').replace('100x100bb', '500x500bb'), item.get('previewUrl', None)
    except Exception:
        pass
    return "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&auto=format&fit=crop&q=80", "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3"

# ==========================================
# 3. Session State Management
# ==========================================
if 'cart_count' not in st.session_state:
    st.session_state.cart_count = 0
if 'current_track_idx' not in st.session_state:
    st.session_state.current_track_idx = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'is_liked' not in st.session_state:
    st.session_state.is_liked = False
if 'features' not in st.session_state:
    st.session_state.features = {"energy": 0.35, "valence": 0.45, "tempo": 78}
if 'playlist' not in st.session_state:
    st.session_state.playlist = [
        {
            "title": "Fern Light",
            "artist": "Helia Marsh",
            "tag": "🍃 #VernalWoods",
            "reason": "จังหวะ Ambient Drone นุ่มนวลผสมเสียงธรรมชาติ บันทึกสดตัดลงแผ่น LPs Cut ครั้งเดียว",
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
# 4. Header Bar
# ==========================================
header_col1, header_col2, header_col3 = st.columns([2, 4, 2])

with header_col1:
    st.markdown("""
        <div style="display:flex; align-items:center; gap:10px; padding:15px 0 0 20px;">
            <svg width="20" height="20" viewBox="0 0 256 256" fill="white">
                <path d="M 256 256 L 128 256 C 198.692 256 256 198.692 256 128 C 256 57.308 198.692 0 128 0 C 57.308 0 0 57.308 0 128 C 0 198.692 57.308 256 128 256 L 0 256 L 0 0 L 256 0 Z M 128 104 C 141.255 104 152 114.745 152 128 C 152 141.255 141.255 152 128 152 C 114.745 152 104 141.255 104 128 C 104 114.745 114.745 104 128 104 Z" />
            </svg>
            <span style="font-size: 1.1rem; font-weight: 500; tracking-tight: -0.02em;">quietpress</span>
        </div>
    """, unsafe_allow_html=True)

with header_col2:
    st.markdown("""
        <div style="display:flex; justify-content:center; gap:30px; padding-top:20px; font-size:0.9rem; color:rgba(255,255,255,0.85);">
            <span style="cursor:pointer;">Anthology</span>
            <span style="cursor:pointer;">Talents</span>
            <span style="cursor:pointer;">Sound diary</span>
            <span style="cursor:pointer;">Playback salon</span>
        </div>
    """, unsafe_allow_html=True)

with header_col3:
    if st.button(f"🛒 Cart ({st.session_state.cart_count})", key="cart_btn"):
        st.session_state.cart_count += 1
        st.rerun()

# ==========================================
# 5. Hero Section (Centered Viewport)
# ==========================================
hero_left, hero_right = st.columns([1.5, 1])

with hero_left:
    st.markdown("""
        <div style="padding-left: 25px; padding-top: 40px;" class="animate-fade-up">
            <div style="display:inline-block; padding: 6px 14px; background: rgba(255,255,255,0.16); border-radius: 8px; font-size:0.8rem; margin-bottom: 20px;">
                Press 04 . Vernal woods
            </div>
            <h1 style="font-size: 3.8rem; font-weight: 400; line-height: 1.1; margin-bottom: 20px;">
                records cut for the<br>calm listener.
            </h1>
            <p style="font-size: 1.05rem; color: rgba(255,255,255,0.85); max-w: 420px; line-height: 1.6; margin-bottom: 25px;">
                Drone, roots, and nature-captured sound on wax LPs. Every disc cut just once, snag it or miss.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Interactive AI Mood Matcher Form
    st.markdown("<div style='padding-left:25px;'>", unsafe_allow_html=True)
    input_col1, input_col2 = st.columns([3, 1])
    with input_col1:
        mood_query = st.text_input("Mood AI Search", placeholder="บอกอารมณ์ของคุณ (เช่น เหงา, สงบ, อยากได้เสียงฝน)...", label_visibility="collapsed")
    with input_col2:
        search_trigger = st.button("✨ Match Track", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Action Buttons
    st.markdown("<div style='padding-left:25px; margin-top:15px;'>", unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        if st.button("Browse the shelves", type="primary", use_container_width=True):
            st.session_state.cart_count += 1
            st.rerun()
    with btn_col2:
        if st.button("Newest arrivals", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx + 1) % len(st.session_state.playlist)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# AI DJ Logic Execution
if search_trigger and mood_query:
    with st.spinner("🎧 AI DJกำลังเทียบเคียงอารมณ์ดนตรี..."):
        e, v, t = 0.3, 0.4, 80.0
        if model:
            try:
                resp = model.generate_content(f"วิเคราะห์อารมณ์ '{mood_query}' ให้ค่า Energy(0-1), Valence(0-1), Tempo(60-200) ตอบสั้นๆ คั่นด้วยจุลภาค เช่น 0.3,0.4,75")
                vals = re.sub(r'[^0-9.,]', '', resp.text).split(',')
                e, v, t = float(vals[0]), float(vals[1]), float(vals[2])
            except Exception:
                pass

        st.session_state.features = {"energy": e, "valence": v, "tempo": t}

        if kmeans and scaler and df_songs is not None:
            try:
                scaled = scaler.transform([[0.5, e, v, t]])
                cluster = kmeans.predict(scaled)[0]
                matched = df_songs[df_songs['cluster_id'] == cluster].sample(min(3, len(df_songs)))
                new_list = []
                for _, r in matched.iterrows():
                    img, prev = fetch_track_metadata(r['track_name'], r['artists'])
                    new_list.append({
                        "title": r['track_name'],
                        "artist": r['artists'],
                        "tag": f"✨ #{mood_query[:10]}",
                        "reason": f"วิเคราะห์พบค่า Energy {e:.2f} & BPM {int(t)} เหมาะกับสภาวะอารมณ์ของคุณในขณะนี้",
                        "img": img,
                        "preview": prev
                    })
                st.session_state.playlist = new_list
                st.session_state.current_track_idx = 0
                st.session_state.is_playing = True
                st.rerun()
            except Exception:
                pass

# ==========================================
# 6. Right Side Widget (Now Playing & 3D Vinyl)
# ==========================================
curr_track = st.session_state.playlist[st.session_state.current_track_idx]

with hero_right:
    st.markdown("<div style='padding-right:25px; padding-top:20px;' class='animate-fade-up'>", unsafe_allow_html=True)
    
    # DJ Perspective Box
    eq_html = '<div style="display:flex; align-items:flex-end; height:14px;"><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span></div>' if st.session_state.is_playing else ''
    st.markdown(f"""
        <div class="liquid-glass" style="padding: 14px; margin-bottom: 12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.7rem; font-weight:bold; color:#93c5fd; text-transform:uppercase;">🤖 AI DJ Perspective</span>
                {eq_html}
            </div>
            <div style="font-size:0.82rem; color:rgba(255,255,255,0.85); line-height:1.4;">
                "{curr_track['reason']}"
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 3D Vinyl Album Card
    spin_class = "vinyl-spin" if st.session_state.is_playing else "vinyl-spin vinyl-pause"
    st.markdown(f"""
        <div style="background:white; border-radius: 18px; padding: 12px; color:#111827; box-shadow: 0 15px 35px rgba(0,0,0,0.4); margin-bottom: 12px;">
            <div style="display:flex; align-items:center; gap: 12px;">
                <div style="position:relative; width: 50px; height: 50px; flex-shrink:0;">
                    <div class="{spin_class}" style="position:absolute; right:-8px; width: 46px; height: 46px; border-radius:50%; background:#171717; border: 1px solid #404040; display:flex; align-items:center; justify-center:center;">
                        <div style="width: 14px; height: 14px; border-radius:50%; background:#1d4ed8;"></div>
                    </div>
                    <img src="{curr_track['img']}" style="position:relative; z-index:2; width: 48px; height: 48px; border-radius:10px; object-fit:cover;" />
                </div>
                <div style="flex:1; min-width:0;">
                    <span style="font-size: 0.65rem; font-weight:bold; color:#1d4ed8; background:#eff6ff; padding: 2px 6px; border-radius: 4px;">
                        {curr_track['tag']}
                    </span>
                    <div style="font-size:0.85rem; font-weight:bold; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px;">
                        {curr_track['artist']} -- {curr_track['title']}
                    </div>
                    <div style="display:flex; align-items:center; gap: 8px; margin-top: 6px;">
                        <div style="flex:1; height:4px; background:#e5e7eb; border-radius:2px; overflow:hidden;">
                            <div style="height:100%; width:{'70%' if st.session_state.is_playing else '30%'}; background:#1d4ed8;"></div>
                        </div>
                        <span style="font-size: 0.65rem; color:#6b7280; font-family:monospace;">0:33 / -1:21</span>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Audio Playback Control Row
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1, 1, 1, 1])
    with ctrl_col1:
        if st.button("⏮ Prev", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx - 1 + len(st.session_state.playlist)) % len(st.session_state.playlist)
            st.rerun()
    with ctrl_col2:
        play_label = "⏸ Pause" if st.session_state.is_playing else "▶ Play"
        if st.button(play_label, type="primary", use_container_width=True):
            st.session_state.is_playing = not st.session_state.is_playing
            st.rerun()
    with ctrl_col3:
        like_label = "💙 Liked" if st.session_state.is_liked else "🤍 Like"
        if st.button(like_label, use_container_width=True):
            st.session_state.is_liked = not st.session_state.is_liked
            st.rerun()
    with ctrl_col4:
        if st.button("Next ⏭", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx + 1) % len(st.session_state.playlist)
            st.rerun()

    # Hidden Native Streamlit Audio Player for Reliable Sound Preview
    if st.session_state.is_playing and curr_track.get('preview'):
        st.audio(curr_track['preview'], autoplay=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 7. Radar Chart & Analytics (Optional Expander)
# ==========================================
with st.expander("📊 ดูค่าวิเคราะห์องค์ประกอบเสียง (Audio Spectrum Radar)"):
    r_col1, r_col2 = st.columns([2, 1])
    with r_col1:
        f = st.session_state.features
        fig = go.Figure(data=go.Scatterpolar(
            r=[f['energy'], f['valence'], f['tempo']/200.0, f['energy']],
            theta=['Energy', 'Valence', 'Tempo (BPM)', 'Energy'],
            fill='toself',
            fillcolor='rgba(29, 78, 216, 0.3)',
            line_color='#1d4ed8'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=False,
            height=240,
            margin=dict(l=30, r=30, t=20, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        st.plotly_chart(fig, use_container_width=True)
    with r_col2:
        st.write("📝 **ประเมินผล AI DJ Matcher**")
        if st.button("👍 โดนใจมาก"):
            st.success("บันทึกข้อมูลเรียบร้อย!")
        if st.button("👎 ยังไม่โดนใจ"):
            st.info("ขอบคุณสำหรับคำแนะนำ!")
