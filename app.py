import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import re
import uuid
import time
import jwt

st.set_page_config(
    page_title="Tableau AI Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 최소한의 Streamlit 기본 UI 제거 ──────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, header, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; }
section[data-testid="stMain"] > div { padding: 0 !important; }
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stVerticalBlock"] { gap: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Config ────────────────────────────────────────────────────────────────────
TABLEAU_URL  = st.secrets.get("TABLEAU_URL",  "https://public.tableau.com")
TABLEAU_VIEW = st.secrets.get("TABLEAU_VIEW", "")
GEMINI_KEY   = st.secrets.get("GEMINI_API_KEY", "")

# ── Tableau Connected App ─────────────────────────────────────────────────────
CA_CLIENT_ID    = st.secrets.get("TABLEAU_CONNECTED_APP_CLIENT_ID", "")
CA_SECRET_ID    = st.secrets.get("TABLEAU_CONNECTED_APP_SECRET_ID", "")
CA_SECRET_VALUE = st.secrets.get("TABLEAU_CONNECTED_APP_SECRET_VALUE", "")
TABLEAU_USER    = st.secrets.get("TABLEAU_USER", "")  # Tableau Cloud 로그인 이메일

def generate_jwt() -> str:
    """Tableau Connected App JWT 토큰 생성"""
    if not (CA_CLIENT_ID and CA_SECRET_ID and CA_SECRET_VALUE):
        return ""
    now = int(time.time())
    payload = {
        "iss": CA_CLIENT_ID,
        "exp": now + 600,   # 10분 유효
        "jti": str(uuid.uuid4()),
        "aud": "tableau",
        "sub": TABLEAU_USER,
        "scp": ["tableau:views:embed", "tableau:metrics:embed"],
    }
    headers = {"kid": CA_SECRET_ID, "iss": CA_CLIENT_ID}
    return jwt.encode(payload, CA_SECRET_VALUE, algorithm="HS256", headers=headers)

VIEWS = [
    {"label": "전사 Summary",  "path": st.secrets.get("VIEW_SUMMARY",  TABLEAU_VIEW)},
    {"label": "유럽영업 BG",   "path": st.secrets.get("VIEW_EUROPE",   TABLEAU_VIEW)},
    {"label": "북미지역 BS",   "path": st.secrets.get("VIEW_NA",       TABLEAU_VIEW)},
    {"label": "해외영업 BS",   "path": st.secrets.get("VIEW_OVERSEAS", TABLEAU_VIEW)},
    {"label": "한국지역 BS",   "path": st.secrets.get("VIEW_KOREA",    TABLEAU_VIEW)},
]

SUGGESTIONS = [
    "영업이익 달성률은?",
    "매출액 Plan vs Actual",
    "환율 영향 분석",
    "원재료 차이 원인",
    "가장 성과 좋은 BG",
]

# ── Query params ──────────────────────────────────────────────────────────────
params     = st.query_params
active_idx = int(params.get("view", 0))
if active_idx >= len(VIEWS):
    active_idx = 0
current_view     = VIEWS[active_idx]
tableau_full_url = f"{TABLEAU_URL.rstrip('/')}/{current_view['path'].lstrip('/')}"

# ── AI ────────────────────────────────────────────────────────────────────────
def build_system_prompt():
    return """당신은 Tableau P&L 대시보드 전문 AI 어시스턴트입니다.
현재 분석 중인 대시보드: "2월 Consolidated P&L Report (연결손익보고)"

## 2월 실적 데이터
- 매출액: Plan 1,470억 / Actual 1,482억 / 달성률 100.9%
- 수량: Plan 3,031천개 / Actual 2,950천개 / 달성률 97.3%
- 매출원가: Plan 996억 / Actual 1,004억 / 달성률 100.8%
- 매출총이익: Plan 473억 / Actual 478억 / 달성률 101.1%
- 판매관리비: Plan 450억 / Actual 434억 / 달성률 96.4%
- 영업이익: Plan 23억 / Actual 44억 / 달성률 191.8%
- 이익률: Plan 1.6% / Actual 3.0%

## 영업이익 요인 분해
계획 23억 → 환율+18 / 원재료단가+1 / 원재료물량-1 / 매출판가-18 / 매출물량+8 / 가공비변동-5 / 가공비고정+3 / 판매비변동-16 → 실적 44억

한국어로 간결하게, 숫자는 억원/% 단위로 답변하세요."""

def get_ai_response(user_msg: str) -> str:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=build_system_prompt(),
    )
    history = []
    for m in st.session_state.messages[:-1]:
        role = "model" if m["role"] == "assistant" else "user"
        history.append({"role": role, "parts": [m["content"]]})
    chat = model.start_chat(history=history)
    return chat.send_message(user_msg).text

# ── Process incoming message ──────────────────────────────────────────────────
incoming = params.get("msg", "")
if incoming:
    last_user = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        None,
    )
    if incoming != last_user:
        st.session_state.messages.append({"role": "user", "content": incoming})
        with st.spinner("답변 생성 중..."):
            reply = get_ai_response(incoming)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        new_params = {k: v for k, v in params.items() if k not in ("msg", "ts")}
        st.query_params.update(new_params)
        st.rerun()

# ── Build messages HTML ───────────────────────────────────────────────────────
def escape(s):
    return (s.replace("&","&amp;").replace("<","&lt;")
             .replace(">","&gt;").replace('"',"&quot;"))

def md_to_html(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    lines = text.split('\n')
    out, in_ul = "", False
    for line in lines:
        if line.startswith('- '):
            if not in_ul:
                out += "<ul>"
                in_ul = True
            out += f"<li>{line[2:]}</li>"
        else:
            if in_ul:
                out += "</ul>"
                in_ul = False
            if line.strip():
                out += f"<p>{line}</p>"
    if in_ul:
        out += "</ul>"
    return out

if not st.session_state.messages:
    msgs_html = """
    <div class="empty-state">
      <div style="font-size:28px;margin-bottom:8px;">&#128202;</div>
      <div class="empty-title">무엇이든 물어보세요</div>
      <div class="empty-sub">대시보드 수치, 달성률, 요인 분석<br>BG별 실적 비교까지 답해드립니다</div>
    </div>"""
else:
    msgs_html = ""
    for m in st.session_state.messages:
        body = md_to_html(m["content"])
        if m["role"] == "user":
            msgs_html += f"""
            <div class="msg-row user">
              <div class="bubble user-bubble">{body}</div>
              <div class="avatar user-av">나</div>
            </div>"""
        else:
            msgs_html += f"""
            <div class="msg-row">
              <div class="avatar ai-av">AI</div>
              <div class="bubble ai-bubble">{body}</div>
            </div>"""

# ── Tab buttons ───────────────────────────────────────────────────────────────
tab_btns = ""
for i, v in enumerate(VIEWS):
    is_active = (i == active_idx)
    tab_btns += f"""
    <button class="tab-btn {'active' if is_active else ''}"
            onclick="gotoView({i})">{v['label']}</button>"""

# ── Chip buttons ──────────────────────────────────────────────────────────────
chips = "".join(
    f'<button class="chip" onclick="sendMsg(\'{s}\')">{s}</button>'
    for s in SUGGESTIONS
)

# ── Full page HTML (single components.html call) ──────────────────────────────
page_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script type="module" src="https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js"></script>
<style>
*, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }}
html, body {{ height:100%; background:#0f1117; overflow:hidden; }}

/* ── Nav ── */
.nav {{
  display:flex; align-items:center; justify-content:space-between;
  padding:11px 20px; background:#161b27; border-bottom:1px solid #1f2937;
  height:52px;
}}
.nav-left {{ display:flex; align-items:center; gap:10px; }}
.nav-icon {{
  width:28px; height:28px; background:#3b82f6; border-radius:7px;
  display:flex; align-items:center; justify-content:center; font-size:14px;
}}
.nav-title {{ font-size:14px; font-weight:600; color:#f1f5f9; }}
.nav-sub   {{ font-size:10px; color:#64748b; margin-top:1px; }}
.nav-badge {{
  font-size:10px; padding:3px 10px;
  background:#1e293b; border:1px solid #334155;
  border-radius:20px; color:#94a3b8;
}}

/* ── Tab bar ── */
.tab-bar {{
  display:flex; gap:5px; padding:7px 14px; height:40px;
  background:#0f1117; border-bottom:1px solid #1f2937; overflow-x:auto;
}}
.tab-bar::-webkit-scrollbar {{ display:none; }}
.tab-btn {{
  font-size:11px; font-weight:500; padding:4px 12px;
  border-radius:6px; border:1px solid #1f2937;
  color:#64748b; background:transparent; cursor:pointer; white-space:nowrap;
  transition:all .15s;
}}
.tab-btn:hover  {{ color:#94a3b8; border-color:#334155; background:#1e293b; }}
.tab-btn.active {{ color:#3b82f6; border-color:#3b82f640; background:#3b82f610; }}

/* ── Main grid ── */
.grid {{
  display:grid; grid-template-columns:1fr 370px;
  height:calc(100vh - 92px);
}}

/* ── Tableau panel ── */
.tableau-panel {{
  background:#0f1117; border-right:1px solid #1f2937;
  padding:12px; display:flex; overflow:hidden;
}}
tableau-viz {{ width:100%; height:100%; border-radius:8px; }}

/* ── Chat panel ── */
.chat-panel {{
  display:flex; flex-direction:column; background:#0f1117; overflow:hidden;
}}
.chat-header {{
  padding:11px 14px; background:#161b27;
  border-bottom:1px solid #1f2937; flex-shrink:0;
}}
.chat-header-title {{ font-size:12px; font-weight:600; color:#e2e8f0; margin-bottom:2px; }}
.chat-header-sub   {{ font-size:10px; color:#475569; }}

/* ── Chips ── */
.chips {{
  display:flex; flex-wrap:wrap; gap:4px; padding:7px 10px;
  border-bottom:1px solid #1f2937; flex-shrink:0; background:#0f1117;
}}
.chip {{
  font-size:10px; padding:3px 9px;
  background:#1e293b; border:1px solid #1f2937;
  border-radius:20px; color:#64748b; cursor:pointer; white-space:nowrap;
  transition:all .15s;
}}
.chip:hover {{ color:#3b82f6; border-color:#3b82f640; background:#3b82f610; }}

/* ── Messages ── */
.messages {{
  flex:1; overflow-y:auto; padding:10px;
  display:flex; flex-direction:column; gap:8px;
  scrollbar-width:thin; scrollbar-color:#1f2937 transparent;
}}
.messages::-webkit-scrollbar {{ width:3px; }}
.messages::-webkit-scrollbar-thumb {{ background:#1f2937; border-radius:3px; }}

.empty-state {{
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:100%; gap:6px; padding:20px;
}}
.empty-title {{ font-size:13px; font-weight:500; color:#64748b; }}
.empty-sub   {{ font-size:11px; color:#334155; text-align:center; line-height:1.7; }}

.msg-row {{ display:flex; gap:7px; align-items:flex-start; }}
.msg-row.user {{ flex-direction:row-reverse; }}
.avatar {{
  width:24px; height:24px; border-radius:6px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-size:9px; font-weight:600;
}}
.ai-av   {{ background:#3b82f6; color:white; }}
.user-av {{ background:#1e293b; border:1px solid #334155; color:#94a3b8; }}
.bubble {{
  max-width:82%; padding:8px 11px; border-radius:10px;
  font-size:11px; line-height:1.65; color:#e2e8f0;
}}
.ai-bubble   {{ background:#161b27; border:1px solid #1f2937; border-bottom-left-radius:3px; }}
.user-bubble {{ background:#1d3461; border:1px solid #2d4a7a; border-bottom-right-radius:3px; color:#bfdbfe; }}
.bubble p    {{ margin:0 0 3px; }}
.bubble ul   {{ margin:3px 0 3px 13px; }}
.bubble li   {{ margin-bottom:2px; color:#cbd5e1; }}
.bubble strong {{ color:#60a5fa; }}
.bubble code   {{ font-size:10px; background:#0f1117; padding:1px 4px; border-radius:3px; color:#7dd3fc; }}

/* ── Input ── */
.input-area {{
  padding:8px 10px 10px; background:#0f1117;
  border-top:1px solid #1f2937; flex-shrink:0;
}}
.input-row {{
  display:flex; gap:5px; align-items:flex-end;
  background:#161b27; border:1px solid #1f2937;
  border-radius:9px; padding:7px 9px;
}}
.input-row:focus-within {{ border-color:#3b82f640; }}
textarea {{
  flex:1; background:transparent; border:none; outline:none;
  color:#e2e8f0; font-size:11px; font-family:'Inter',sans-serif;
  resize:none; line-height:1.5; max-height:80px; scrollbar-width:none;
}}
textarea::placeholder {{ color:#334155; }}
.send-btn {{
  width:26px; height:26px; border-radius:6px; border:none;
  background:#3b82f6; color:white; cursor:pointer; font-size:13px; flex-shrink:0;
}}
.send-btn:hover {{ background:#2563eb; }}
.hint {{ font-size:9px; color:#1e293b; margin-top:4px; text-align:center; }}
</style>
</head>
<body>

<!-- Nav -->
<div class="nav">
  <div class="nav-left">
    <div class="nav-icon">&#128202;</div>
    <div>
      <div class="nav-title">Tableau AI Assistant</div>
      <div class="nav-sub">P&amp;L 리포트 분석</div>
    </div>
  </div>
  <div class="nav-badge">Gemini 1.5 Flash + Tableau MCP</div>
</div>

<!-- Tabs -->
<div class="tab-bar">{tab_btns}</div>

<!-- Grid -->
<div class="grid">

  <!-- Tableau -->
  <div class="tableau-panel">
    <tableau-viz id="tviz" src="{tableau_full_url}" token="{generate_jwt()}" toolbar="hidden" hide-tabs="true"></tableau-viz>
  </div>

  <!-- Chat -->
  <div class="chat-panel">
    <div class="chat-header">
      <div class="chat-header-title">&#129302; AI 분석 어시스턴트</div>
      <div class="chat-header-sub">P&amp;L 데이터에 대해 자유롭게 질문하세요</div>
    </div>

    <div class="chips">{chips}</div>

    <div class="messages" id="msgs">{msgs_html}</div>

    <div class="input-area">
      <div class="input-row">
        <textarea id="inp" rows="1" placeholder="질문을 입력하세요... (Enter 전송)"></textarea>
        <button class="send-btn" onclick="send()">&#8593;</button>
      </div>
      <div class="hint">Gemini 1.5 Flash powered · Tableau MCP connected</div>
    </div>
  </div>

</div>

<script>
const msgs = document.getElementById('msgs');
if (msgs) msgs.scrollTop = msgs.scrollHeight;

const ta = document.getElementById('inp');
if (ta) {{
  ta.addEventListener('input', () => {{
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 80) + 'px';
  }});
  ta.addEventListener('keydown', e => {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); send(); }}
  }});
}}

function gotoView(idx) {{
  const url = new URL(window.parent.location.href);
  url.searchParams.set('view', idx);
  window.parent.location.href = url.toString();
}}

function sendMsg(text) {{
  const url = new URL(window.parent.location.href);
  url.searchParams.set('msg', encodeURIComponent(text));
  url.searchParams.set('ts', Date.now());
  window.parent.location.href = url.toString();
}}

function send() {{
  const msg = ta ? ta.value.trim() : '';
  if (msg) sendMsg(msg);
}}
</script>
</body>
</html>"""

components.html(page_html, height=800, scrolling=False)
