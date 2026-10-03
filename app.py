import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
import google.generativeai as genai
import requests
import json
import re

# ==========================================
# 1. Page Config & CSS
# ==========================================
st.set_page_config(
    page_title="quietpress -- vinyl record label",
    page_icon="💿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Helper Function ป้องกันปัญหา Streamlit แสดงผล HTML เป็น Code Block
def render_html(html_str):
    cleaned = "\n".join([line.strip() for line in html_str.split("\n")])
    st.markdown(cleaned, unsafe_allow_html=True)

# CSS Customization
render_html("""
<link rel="stylesheet" href="https://db.onlinewebfonts.com/c/a64ff11d2c24584c767f6257e880dc65?family=Helvetica+Regular">

<style>
    /* Clean up default Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {
        padding: 1rem 2rem !important;
        max-width: 100% !important;
    }
    div[data-testid="stToolbar"] {display: none;}
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Helvetica Regular', Helvetica, Arial, sans-serif !important;
        background-color: #050505;
        color: #ffffff;
        overflow-x: hidden;
    }

    /* Boomerang Background Video Layer */
    .bg-video-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 0;
        overflow: hidden;
        pointer-events: none;
        transform: scale(1.05);
        transform-origin: center;
    }
    .bg-video-container video, .bg-video-container canvas {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    /* Liquid Glass Styling */
    .liquid-glass {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 12px 32px 0 rgba(0, 0, 0, 0.35);
        border-radius: 18px;
    }

    /* Animations */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(15px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-fade-up {
        animation: fadeUp 0.5s ease-out forwards;
    }

    /* Equalizer White Bars Animation */
    @keyframes equalBlink {
        0%, 100% { height: 4px; }
        50% { height: 18px; }
    }
    .eq-bar-white {
        width: 3px;
        background: #ffffff;
        border-radius: 2px;
        animation: equalBlink 0.7s ease-in-out infinite alternate;
    }
    .eq-bar-white:nth-child(1) { animation-delay: 0.1s; }
    .eq-bar-white:nth-child(2) { animation-delay: 0.3s; }
    .eq-bar-white:nth-child(3) { animation-delay: 0.2s; }
    .eq-bar-white:nth-child(4) { animation-delay: 0.4s; }

    /* Custom White Pill Buttons for Player Controls */
    .pill-btn div[data-testid="stButton"] > button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border-radius: 25px !important;
        border: none !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        height: 38px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.25) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    .pill-btn div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.35) !important;
        background-color: #ffffff !important;
        color: #2563eb !important;
    }

    /* Form Input Customization */
    .stTextInput input {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 10px !important;
        font-size: 0.85rem !important;
        height: 38px !important;
    }
</style>

<!-- Background Overlay Video -->
<div class="bg-video-container">
    <video id="bgVid" autoplay muted playsinline crossorigin="anonymous">
        <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260611_183632_c311af08-e4b7-458f-81e7-79847a49b3d3.mp4" type="video/mp4">
    </video>
    <canvas id="bgCanv" style="display:none;"></canvas>
</div>

<script>
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
""")

# ==========================================
# 2. Gemini API & ML Model Setup
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
# 3. Session State
# ==========================================
if 'cart_count' not in st.session_state:
    st.session_state.cart_count = 0
if 'current_track_idx' not in st.session_state:
    st.session_state.current_track_idx = 0
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = True
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
# 4. Navigation Header
# ==========================================
header_left, header_mid, header_right = st.columns([2, 5, 2])

with header_left:
    render_html("""
        <div style="display:flex; align-items:center; gap:8px;">
            <svg width="18" height="18" viewBox="0 0 256 256" fill="white">
                <path d="M 256 256 L 128 256 C 198.692 256 256 198.692 256 128 C 256 57.308 198.692 0 128 0 C 57.308 0 0 57.308 0 128 C 0 198.692 57.308 256 128 256 L 0 256 L 0 0 L 256 0 Z M 128 104 C 141.255 104 152 114.745 152 128 C 152 141.255 141.255 152 128 152 C 114.745 152 104 141.255 104 128 C 104 114.745 114.745 104 128 104 Z" />
            </svg>
            <span style="font-size:1rem; font-weight:500;">quietpress</span>
        </div>
    """)

with header_mid:
    render_html("""
        <div style="display:flex; justify-content:center; gap:25px; font-size:0.85rem; color:rgba(255,255,255,0.8);">
            <span>Anthology</span>
            <span>Talents</span>
            <span>Sound diary</span>
            <span>Playback salon</span>
        </div>
    """)

with header_right:
    if st.button(f"🛒 Cart ({st.session_state.cart_count})", key="cart_btn"):
        st.session_state.cart_count += 1
        st.rerun()

# ==========================================
# 5. Left Hero Section
# ==========================================
left_col, right_col = st.columns([1.2, 1])

with left_col:
    render_html("""
        <div style="padding-top: 15px;" class="animate-fade-up">
            <div style="display:inline-block; padding: 4px 12px; background: rgba(255,255,255,0.12); border-radius: 6px; font-size:0.75rem; margin-bottom: 10px;">
                Press 04 . Vernal woods
            </div>
            <h1 style="font-size: 3rem; font-weight: 400; line-height: 1.1; margin-bottom: 10px;">
                records cut for the<br>calm listener.
            </h1>
            <p style="font-size: 0.9rem; color: rgba(255,255,255,0.8); max-width: 360px; line-height: 1.4; margin-bottom: 15px;">
                Drone, roots, and nature-captured sound on wax LPs. Every disc cut just once, snag it or miss.
            </p>
        </div>
    """)

    render_html("<div style='max-width: 380px;' class='liquid-glass p-3 mb-2'>")
    
    m_col1, m_col2 = st.columns([2.5, 1])
    with m_col1:
        mood_query = st.text_input("Mood AI", placeholder="ระบุอารมณ์ (เช่น เหงา, ฝนตก)...", label_visibility="collapsed")
    with m_col2:
        search_trigger = st.button("✨ Match", use_container_width=True)
        
    b_col1, b_col2 = st.columns([1, 1])
    with b_col1:
        if st.button("Browse shelves", type="primary", use_container_width=True):
            st.session_state.cart_count += 1
            st.rerun()
    with b_col2:
        if st.button("Newest arrivals", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx + 1) % len(st.session_state.playlist)
            st.rerun()
            
    render_html("</div>")

if search_trigger and mood_query:
    with st.spinner("🎧 AI DJ กำลังจัดรายการ..."):
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
# 6. Bottom-Right Player & AI DJ Widget
# ==========================================
curr_track = st.session_state.playlist[st.session_state.current_track_idx]

with right_col:
    # คอนเทนเนอร์รวมเครื่องเล่นไว้ขวาล่าง
    render_html("<div style='margin-top: 15px; max-width: 330px; margin-left: auto;' class='animate-fade-up'>")
    
    # 📌 1. กล่องข้อความ AI DJ PERSPECTIVE (Liquid Glass ข้างบน)
    dj_card = f"""
    <div class="liquid-glass" style="padding: 12px 14px; margin-bottom: 12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <span style="font-size:0.68rem; font-weight:bold; color:#93c5fd; letter-spacing:0.5px; text-transform:uppercase;">🤖 AI DJ PERSPECTIVE</span>
        </div>
        <div style="font-size:0.78rem; color:rgba(255,255,255,0.9); line-height:1.35; word-break: break-word;">
            "{curr_track['reason']}"
        </div>
    </div>
    """
    render_html(dj_card)

    # 📌 2. เครื่องเล่นเพลงทรงแคปซูลสีขาว (ตรงตามภาพตัวอย่าง)
    eq_bars = """
    <div style="display:flex; align-items:flex-end; gap:2px; height:16px;">
        <span class="eq-bar-white"></span>
        <span class="eq-bar-white"></span>
        <span class="eq-bar-white"></span>
        <span class="eq-bar-white"></span>
    </div>
    """ if st.session_state.is_playing else """
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
        <path d="M9 18V5l12-2v13M9 9l12-2M6 18a3 3 0 100-6 3 3 0 000 6zM18 16a3 3 0 100-6 3 3 0 000 6z"/>
    </svg>
    """

    player_card = f"""
    <div style="background: #ffffff; border-radius: 20px; padding: 12px 16px; color: #0f172a; box-shadow: 0 12px 30px rgba(0,0,0,0.35); display: flex; align-items: center; gap: 14px; margin-bottom: 10px;">
        <div style="background: #2563eb; width: 44px; height: 44px; border-radius: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);">
            {eq_bars}
        </div>
        <div style="flex: 1; min-width: 0;">
            <div style="font-size: 0.85rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #0f172a; margin-bottom: 4px;">
                {curr_track['artist']} — {curr_track['title']}
            </div>
            <div style="height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; margin-bottom: 4px;">
                <div style="height: 100%; width: {'65%' if st.session_state.is_playing else '30%'}; background: #2563eb; border-radius: 2px; transition: width 0.3s ease;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #64748b; font-weight: 500;">
                <span>0:33</span>
                <span>-1:21</span>
            </div>
        </div>
    </div>
    """
    render_html(player_card)

    # 📌 3. ปุ่มควบคุมเครื่องเล่นเพลงแบบ Pill Buttons สีขาว (ด้านล่าง)
    render_html("<div class='pill-btn'>")
    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1, 1.2])
    
    with ctrl1:
        if st.button("Prev", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx - 1 + len(st.session_state.playlist)) % len(st.session_state.playlist)
            st.rerun()
            
    with ctrl2:
        like_symbol = "💙" if st.session_state.is_liked else "🤍"
        if st.button(like_symbol, use_container_width=True):
            st.session_state.is_liked = not st.session_state.is_liked
            st.session_state.is_playing = not st.session_state.is_playing
            st.rerun()
            
    with ctrl3:
        if st.button("Next", use_container_width=True):
            st.session_state.current_track_idx = (st.session_state.current_track_idx + 1) % len(st.session_state.playlist)
            st.rerun()
            
    render_html("</div>")

    # เล่นเสียงตัวอย่าง
    if st.session_state.is_playing and curr_track.get('preview'):
        st.audio(curr_track['preview'], autoplay=True)

    render_html("</div>")

# ==========================================
# 7. Audio Spectrum Radar Chart Expander
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
            height=200,
            margin=dict(l=20, r=20, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        st.plotly_chart(fig, use_container_width=True)
    with r_col2:
        st.write("📝 **ผลลัพธ์ AI DJ Matcher**")
        if st.button("👍 โดนใจมาก"):
            st.success("บันทึกความชอบแล้ว!")
        if st.button("👎 ยังไม่โดนใจ"):
            st.info("ขอบคุณสำหรับคำแนะนำ!")
