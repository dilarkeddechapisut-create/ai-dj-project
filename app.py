import streamlit as st
from streamlit_mic_recorder import speech_to_text

# นำเข้า Service ต่างๆ
from ai_service import get_playlist_from_ai
from spotify_service import search_spotify_track
from stats_service import create_radar_chart
from preview_service import get_track_preview

# ==========================================
# 1. ตั้งค่าหน้าเพจ & CSS + Video Background
# ==========================================
st.set_page_config(page_title="AI DJ Mood Matcher", page_icon="🎧", layout="centered")

BG_VIDEO_URL = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_083109_283f3553-e28f-428b-a723-d639c617eb2b.mp4"

st.markdown(f"""
<style>
    /* จัดสไตล์ตัววิดีโอเป็น Background เต็มจอ */
    #bg-video {{
        position: fixed;
        right: 0;
        bottom: 0;
        min-width: 100%;
        min-height: 100%;
        width: auto;
        height: auto;
        z-index: -100;
        object-fit: cover;
        filter: brightness(0.4);
    }}

    /* ลบแถบพื้นหลังดำยาวของ Mic Recorder Component (แก้ไขปุ่มให้เหมือนรูปสอง) */
    div[data-testid="stCustomComponentV1"],
    div[data-testid="stCustomComponentV1"] iframe,
    iframe[title*="speech_to_text"],
    iframe[title*="streamlit_mic_recorder"] {{
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
    }}

    /* ตกแต่ง Header ตรงกลาง */
    .main-header {{
        text-align: center;
        margin-top: 10px;
        margin-bottom: 5px;
    }}
    .main-header h1 {{
        font-size: 2.3rem;
        font-weight: 800;
        color: #58a6ff;
        display: inline-block;
        margin-bottom: 8px;
        text-shadow: 0 2px 10px rgba(0,0,0,0.8);
    }}
    .main-header p {{
        color: #c9d1d9;
        font-size: 1rem;
        margin-bottom: 25px;
        text-shadow: 0 1px 5px rgba(0,0,0,0.8);
    }}

    /* หัวข้อและ Label */
    .section-title {{
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 10px;
        margin-bottom: 12px;
        color: #ffffff;
        text-shadow: 0 1px 5px rgba(0,0,0,0.8);
    }}

    .input-label {{
        font-weight: 600;
        color: #ffffff;
        margin-top: 15px;
        margin-bottom: 6px;
        font-size: 0.95rem;
        text-shadow: 0 1px 5px rgba(0,0,0,0.8);
    }}

    /* ปรับแต่ง Text Area ให้โปร่งแสงรับกับวิดีโอ */
    div[data-testid="stTextArea"] textarea {{
        background-color: rgba(22, 27, 34, 0.75) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 10px !important;
        font-size: 15px !important;
        backdrop-filter: blur(5px);
    }}
    
    div[data-testid="stTextArea"] textarea:focus {{
        border-color: #ff5252 !important;
        box-shadow: 0 0 10px rgba(255, 82, 82, 0.5) !important;
    }}

    /* Flip Card */
    .flip-card {{
        background-color: transparent;
        width: 100%;
        height: 300px;
        perspective: 1000px;
        margin-bottom: 20px;
    }}
    .flip-card-inner {{
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: transform 0.6s;
        transform-style: preserve-3d;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.5);
        border-radius: 15px;
    }}
    .flip-card:hover .flip-card-inner {{
        transform: rotateY(180deg);
    }}
    .flip-card-front, .flip-card-back {{
        position: absolute;
        width: 100%;
        height: 100%;
        backface-visibility: hidden;
        border-radius: 15px;
    }}
    .flip-card-front {{
        background-color: #bbb;
        color: black;
    }}
    .flip-card-front img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 15px;
    }}
    .flip-card-back {{
        background-color: #1DB954;
        color: white;
        transform: rotateY(180deg);
        padding: 20px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }}

    /* Floating Player Box */
    div[data-key="floating_player_box"],
    div.st-key-floating_player_box,
    div[class*="st-key-floating_player_box"],
    div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) {{
        position: fixed !important;
        bottom: 25px !important;
        right: 25px !important;
        width: 350px !important;
        max-width: calc(100vw - 40px) !important;
        height: auto !important;
        background: #121212 !important;
        border: 1.5px solid #1DB954 !important;
        border-radius: 16px !important;
        padding: 12px 14px 10px 14px !important;
        z-index: 999999 !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8) !important;
    }}

    div[data-key="floating_player_box"] div[data-testid="stVerticalBlock"],
    div[class*="st-key-floating_player_box"] div[data-testid="stVerticalBlock"],
    div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) div[data-testid="stVerticalBlock"] {{
        gap: 0.3rem !important;
    }}

    div[data-key="floating_player_box"] div[data-testid="stAudio"],
    div[class*="st-key-floating_player_box"] div[data-testid="stAudio"],
    div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) div[data-testid="stAudio"] {{
        margin: 2px 0px !important;
        padding: 0px !important;
    }}

    div[data-key="floating_player_box"] audio,
    div[class*="st-key-floating_player_box"] audio,
    div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) audio {{
        border-radius: 8px !important;
        width: 100% !important;
    }}

    div[data-key="floating_player_box"] button,
    div[class*="st-key-floating_player_box"] button,
    div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) button {{
        border-radius: 8px !important;
    }}

    @media (max-width: 768px) {{
        div[data-key="floating_player_box"],
        div[class*="st-key-floating_player_box"],
        div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker) {{
            bottom: 15px !important;
            right: 15px !important;
            left: 15px !important;
            width: calc(100vw - 30px) !important;
        }}
    }}
</style>

<!-- HTML Tag วิดีโอพื้นหลัง -->
<video autoplay loop muted playsinline id="bg-video">
    <source src="{BG_VIDEO_URL}" type="video/mp4">
</video>

<!-- JS ช่วยลบสีพื้นหลังดำข้างใน iframe ของ Mic Recorder -->
<script>
(function fixMicIframeBg() {{
    function cleanIframe() {{
        var doc = window.parent ? window.parent.document : document;
        var iframes = doc.querySelectorAll('iframe');
        iframes.forEach(function(iframe) {{
            try {{
                var innerDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (innerDoc) {{
                    if (innerDoc.body) {{
                        innerDoc.body.style.backgroundColor = 'transparent';
                        innerDoc.body.style.background = 'transparent';
                    }}
                    if (innerDoc.documentElement) {{
                        innerDoc.documentElement.style.backgroundColor = 'transparent';
                        innerDoc.documentElement.style.background = 'transparent';
                    }}
                }}
            }} catch(e) {{}}
        }});
    }}
    cleanIframe();
    setInterval(cleanIframe, 300);
}})();
</script>
""", unsafe_allow_html=True)

# ==========================================
# 2. State Management
# ==========================================
if 'playlist' not in st.session_state:
    st.session_state.playlist = [] 
if 'ai_message' not in st.session_state:
    st.session_state.ai_message = "" 
if 'current_preview_url' not in st.session_state:
    st.session_state.current_preview_url = None 
if 'current_track_name' not in st.session_state:
    st.session_state.current_track_name = "" 
if 'current_track_index' not in st.session_state:
    st.session_state.current_track_index = 0

# ==========================================
# 3. Header ตรงกลาง
# ==========================================
st.markdown("""
<div class="main-header">
    <h1>🎧 AI DJ Mood Matcher</h1>
    <p>บอกความรู้สึกของคุณ แล้วให้ AI DJ คัดสรรบทเพลงพร้อมมุมมองเฉพาะคุณ</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 4. Form Layout
# ==========================================
st.markdown('<div class="section-title">🎙️ เล่าความรู้สึกของคุณผ่านเสียงหรือพิมพ์ข้อความ</div>', unsafe_allow_html=True)

# 1. ปุ่มพูดความรู้สึก (ไมโครโฟน)
text_from_mic = speech_to_text(
    language='th-TH', 
    start_prompt="🎙️ กดเพื่อพูดความรู้สึก", 
    stop_prompt="🛑 กดอีกครั้งเพื่อหยุด", 
    just_once=False,
    key='STT'
)

# 2. ช่องใส่ความรู้สึก
st.markdown('<div class="input-label">ความรู้สึกของคุณ:</div>', unsafe_allow_html=True)
default_text = text_from_mic if text_from_mic else ""

mood_text = st.text_area(
    "ความรู้สึกของคุณ:",
    value=default_text,
    placeholder="เช่น วันนี้เลิกงานแล้ว เหนื่อยมากๆ อยากหาเพลงชิลๆ ฟังผ่อนคลาย...",
    height=100,
    label_visibility="collapsed"
)

# 3. Slider เลือกจำนวนเพลง
st.markdown('<div class="input-label">🎵 จำนวนเพลงที่ต้องการสุ่มจัด:</div>', unsafe_allow_html=True)
num_songs = st.slider(
    "จำนวนเพลงที่ต้องการสุ่มจัด:",
    min_value=3,
    max_value=12,
    value=5,
    label_visibility="collapsed"
)

# 4. ปุ่มจัดเพลงทันที
if st.button("✨ ให้ AI DJ จัดเพลงให้ทันที", type="primary", use_container_width=True):
    if mood_text:
        with st.spinner("AI กำลังวิเคราะห์ความรู้สึกและค้นหาเพลง..."):
            ai_result = get_playlist_from_ai(mood_text, num_songs)
            
            if ai_result:
                st.session_state.ai_message = ai_result['encouragement']
                valid_tracks = []
                
                for song in ai_result['songs']:
                    try:
                        track_info = search_spotify_track(song['title'], song['artist'])
                    except Exception:
                        track_info = None

                    img_url, preview_url, full_url = get_track_preview(song['title'], song['artist'])
                    
                    if not track_info:
                        track_info = {
                            'name': song['title'],
                            'artist': song['artist'],
                            'album_cover': img_url if img_url else "https://via.placeholder.com/500?text=No+Cover",
                            'preview_url': preview_url,
                            'spotify_url': full_url if full_url else "#"
                        }
                    else:
                        if preview_url: 
                            track_info['preview_url'] = preview_url
                        if img_url: 
                            track_info['album_cover'] = img_url
                        if not track_info.get('spotify_url') and full_url: 
                            track_info['spotify_url'] = full_url
                    
                    track_info['reason'] = song['reason']
                    valid_tracks.append(track_info)
                
                st.session_state.playlist = valid_tracks
                st.session_state.current_track_index = 0
    else:
        st.warning("⚠️️ กรุณาพิมพ์หรือพูดความรู้สึกของคุณก่อนครับ")

# ==========================================
# 5. ส่วนแสดงผล Playlist
# ==========================================
if len(st.session_state.playlist) > 0:
    st.success("🎉 จัดเพลย์ลิสต์เสร็จเรียบร้อย!")
    st.markdown(f"### 💌 ข้อความจาก AI DJ:\n> *{st.session_state.ai_message}*")
    st.divider()
    
    cols = st.columns(3)
    for i, track_info in enumerate(st.session_state.playlist):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="flip-card">
                <div class="flip-card-inner">
                <div class="flip-card-front">
                    <img src="{track_info['album_cover']}" alt="Cover">
                </div>
                <div class="flip-card-back">
                    <h4>{track_info['name']}</h4>
                    <p>{track_info['artist']}</p>
                    <hr/>
                    <p style="font-size: 0.9em; font-style: italic;">{track_info.get('reason', '')}</p>
                </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if track_info.get('preview_url'):
                if st.button("▶️ ฟังตัวอย่าง", key=f"play_{i}", use_container_width=True):
                    st.session_state.current_preview_url = track_info['preview_url']
                    st.session_state.current_track_name = track_info['name']
                    st.session_state.current_track_index = i
                    st.rerun() 
            else:
                st.button("❌ ไม่มีตัวอย่าง", key=f"no_play_{i}", disabled=True, use_container_width=True)
            
            st.link_button(
                "🟢 เปิดฟังบน Spotify", 
                track_info.get('spotify_url', '#'), 
                use_container_width=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📈 วิเคราะห์สถิติของ Playlist")
    try:
        fig = create_radar_chart(st.session_state.playlist)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("ไม่สามารถสร้างกราฟสถิติได้")

# ==========================================
# 6. Floating Player
# ==========================================
if st.session_state.current_preview_url and len(st.session_state.playlist) > 0:
    with st.container(key="floating_player_box"):
        st.markdown('<div class="floating-marker"></div>', unsafe_allow_html=True)
        
        curr_idx = st.session_state.get('current_track_index', 0)
        total_songs = len(st.session_state.playlist)
        
        head_c1, head_c2 = st.columns([85, 15])
        with head_c1:
            st.markdown(
                f"<div id='drag-handle' style='cursor: grab; user-select: none; color:#1DB954; font-weight:bold; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:2px 0;'>"
                f"⋮⋮ 🎵 {st.session_state.current_track_name} <span style='color:#888; font-size:11px;'>({curr_idx + 1}/{total_songs})</span></div>",
                unsafe_allow_html=True
            )
        with head_c2:
            if st.button("✖", key="close_player", use_container_width=True):
                st.session_state.current_preview_url = None
                st.session_state.current_track_name = ""
                st.rerun()

        st.audio(st.session_state.current_preview_url, format="audio/mp3", autoplay=True)
        
        ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([1, 1, 1])
        with ctrl_c1:
            if st.button("⏮️ ก่อนหน้า", key="prev_track", use_container_width=True):
                prev_idx = (curr_idx - 1) % total_songs
                st.session_state.current_track_index = prev_idx
                next_track = st.session_state.playlist[prev_idx]
                st.session_state.current_preview_url = next_track.get('preview_url')
                st.session_state.current_track_name = next_track.get('name')
                st.rerun()
        with ctrl_c2:
            st.markdown("<div style='text-align:center; font-size:11px; color:#888; line-height:38px; font-weight:bold;'>AI DJ</div>", unsafe_allow_html=True)
        with ctrl_c3:
            if st.button("ถัดไป ⏭️", key="next_track", use_container_width=True):
                next_idx = (curr_idx + 1) % total_songs
                st.session_state.current_track_index = next_idx
                next_track = st.session_state.playlist[next_idx]
                st.session_state.current_preview_url = next_track.get('preview_url')
                st.session_state.current_track_name = next_track.get('name')
                st.rerun()

    st.markdown("""
    <script>
    (function() {
        function initDrag() {
            var doc = window.parent ? window.parent.document : document;
            
            var player = doc.querySelector('div[data-key="floating_player_box"]') || 
                         doc.querySelector('div[class*="st-key-floating_player_box"]') ||
                         doc.querySelector('div[data-testid="stVerticalBlock"]:has(> div > div > div.floating-marker)');
            
            var handle = doc.querySelector('#drag-handle');
            
            if (!player || !handle) {
                setTimeout(initDrag, 200);
                return;
            }

            if (handle.getAttribute('data-drag-attached') === 'true') return;
            handle.setAttribute('data-drag-attached', 'true');

            var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

            handle.onmousedown = function(e) {
                e = e || window.event;
                e.preventDefault();
                
                pos3 = e.clientX;
                pos4 = e.clientY;

                var rect = player.getBoundingClientRect();

                doc.onmouseup = function() {
                    doc.onmouseup = null;
                    doc.onmousemove = null;
                };

                doc.onmousemove = function(e) {
                    e = e || window.event;
                    e.preventDefault();

                    pos1 = pos3 - e.clientX;
                    pos2 = pos4 - e.clientY;
                    pos3 = e.clientX;
                    pos4 = e.clientY;

                    rect = player.getBoundingClientRect();

                    player.style.position = 'fixed';
                    player.style.top = (rect.top - pos2) + 'px';
                    player.style.left = (rect.left - pos1) + 'px';
                    player.style.bottom = 'auto';
                    player.style.right = 'auto';
                    player.style.margin = '0';
                };
            };
        }

        initDrag();
        setTimeout(initDrag, 500);
    })();
    </script>
    """, unsafe_allow_html=True)
