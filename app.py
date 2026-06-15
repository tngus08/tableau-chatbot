import streamlit as st
import google.generativeai as genai
import re
from tableau_mcp import get_tableau_context, fetch_view_data, search_tableau_content

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tableau AI Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject custom CSS + Tableau Embedding API v3 ──────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script type="module" src="https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js"></script>

<style>
  /* ── Reset & base ── */
  [data-testid="stAppViewContainer"] { background: #0f1117; }
  [data-testid="stHeader"] { background: transparent; }
  section[data-testid="stMain"] > div { padding-top: 0 !important; }
  * { font-family: 'Inter', sans-serif; box-sizing: border-box; }

  /* ── Top nav bar ── */
  .nav-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 28px; background: #161b27;
    border-bottom: 1px solid #1f2937;
    position: sticky; top: 0; z-index: 100;
  }
  .nav-logo { display: flex; align-items: center; gap: 10px; }
  .nav-logo-icon {
    width: 32px; height: 32px; background: linear-gradient(135deg, #3b82f6, #6366f1);
    border-radius: 8px; display: flex; align-items: center; justify-content: center;
    font-size: 16px;
  }
  .nav-title { font-size: 15px; font-weight: 600; color: #f1f5f9; }
  .nav-subtitle { font-size: 11px; color: #64748b; margin-top: 1px; }
  .nav-badge {
    font-size: 11px; font-weight: 500; padding: 4px 10px;
    background: #1e293b; border: 1px solid #334155;
    border-radius: 20px; color: #94a3b8;
  }

  /* ── Main layout ── */
  .main-grid {
    display: grid;
    grid-template-columns: 1fr 400px;
    gap: 0;
    height: calc(100vh - 61px);
    overflow: hidden;
  }

  /* ── Tableau panel ── */
  .tableau-panel {
    background: #0f1117;
    border-right: 1px solid #1f2937;
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    padding: 14px 20px; background: #161b27;
    border-bottom: 1px solid #1f2937;
    display: flex; align-items: center; justify-content: space-between;
  }
  .panel-header-title {
    font-size: 13px; font-weight: 600; color: #e2e8f0;
    display: flex; align-items: center; gap: 8px;
  }
  .panel-header-title::before {
    content: ''; width: 8px; height: 8px; border-radius: 50%;
    background: #22c55e; display: inline-block;
    box-shadow: 0 0 6px #22c55e88;
  }
  .view-tabs {
    display: flex; gap: 6px; padding: 10px 20px;
    background: #0f1117; border-bottom: 1px solid #1f2937;
    overflow-x: auto; scrollbar-width: none;
  }
  .view-tabs::-webkit-scrollbar { display: none; }
  .view-tab {
    font-size: 12px; font-weight: 500; padding: 5px 14px;
    border-radius: 6px; border: 1px solid #1f2937;
    color: #64748b; background: transparent;
    cursor: pointer; white-space: nowrap; transition: all 0.15s;
  }
  .view-tab:hover { color: #94a3b8; border-color: #334155; background: #1e293b; }
  .view-tab.active {
    color: #3b82f6; border-color: #3b82f640;
    background: #3b82f610;
  }
  .tableau-wrapper {
    flex: 1; padding: 16px; overflow: hidden;
    display: flex; align-items: stretch;
  }
  tableau-viz {
    width: 100%; height: 100%;
    border-radius: 10px; overflow: hidden;
  }

  /* ── Chat panel ── */
  .chat-panel {
    background: #0f1117;
    display: flex; flex-direction: column;
    height: 100%;
  }
  .chat-header {
    padding: 14px 20px; background: #161b27;
    border-bottom: 1px solid #1f2937;
    flex-shrink: 0;
  }
  .chat-header-title {
    font-size: 13px; font-weight: 600; color: #e2e8f0;
    display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
  }
  .chat-header-desc { font-size: 11px; color: #475569; }

  /* ── Suggestion chips ── */
  .chips-wrap {
    padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 6px;
    border-bottom: 1px solid #1f2937; flex-shrink: 0;
    background: #0f1117;
  }
  .chip {
    font-size: 11px; padding: 5px 11px;
    background: #1e293b; border: 1px solid #1f2937;
    border-radius: 20px; color: #64748b;
    cursor: pointer; transition: all 0.15s;
    white-space: nowrap;
  }
  .chip:hover { color: #3b82f6; border-color: #3b82f640; background: #3b82f610; }

  /* ── Messages area ── */
  .messages-scroll {
    flex: 1; overflow-y: auto; padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
    scrollbar-width: thin; scrollbar-color: #1f2937 transparent;
  }
  .messages-scroll::-webkit-scrollbar { width: 4px; }
  .messages-scroll::-webkit-scrollbar-track { background: transparent; }
  .messages-scroll::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 4px; }

  .msg { display: flex; gap: 10px; align-items: flex-start; }
  .msg.user { flex-direction: row-reverse; }
  .msg-avatar {
    width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 600;
  }
  .msg-avatar.ai {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    color: white; font-size: 11px;
  }
  .msg-avatar.user {
    background: #1e293b; border: 1px solid #334155;
    color: #94a3b8; font-size: 11px;
  }
  .msg-bubble {
    max-width: 82%; padding: 10px 13px; border-radius: 12px;
    font-size: 13px; line-height: 1.6; color: #e2e8f0;
  }
  .msg.ai .msg-bubble {
    background: #161b27; border: 1px solid #1f2937;
    border-bottom-left-radius: 4px;
  }
  .msg.user .msg-bubble {
    background: #1d3461; border: 1px solid #2d4a7a;
    border-bottom-right-radius: 4px; color: #bfdbfe;
  }
  .msg-bubble strong { color: #60a5fa; font-weight: 600; }
  .msg-bubble ul { margin: 6px 0 0 16px; padding: 0; }
  .msg-bubble li { margin-bottom: 4px; color: #cbd5e1; }
  .msg-bubble code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; background: #0f1117;
    padding: 1px 5px; border-radius: 4px; color: #7dd3fc;
  }

  /* ── Typing indicator ── */
  .typing {
    display: flex; gap: 5px; align-items: center;
    padding: 10px 14px; background: #161b27;
    border: 1px solid #1f2937; border-radius: 12px;
    border-bottom-left-radius: 4px; width: fit-content;
  }
  .typing span {
    width: 6px; height: 6px; background: #475569;
    border-radius: 50%; animation: bounce 1.2s infinite;
  }
  .typing span:nth-child(2) { animation-delay: 0.2s; }
  .typing span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%,60%,100% { transform: translateY(0); }
    30% { transform: translateY(-5px); opacity: 1; }
  }

  /* ── Input area ── */
  .input-area {
    padding: 12px 16px 16px; background: #0f1117;
    border-top: 1px solid #1f2937; flex-shrink: 0;
  }
  .input-row {
    display: flex; gap: 8px; align-items: flex-end;
    background: #161b27; border: 1px solid #1f2937;
    border-radius: 12px; padding: 10px 12px;
    transition: border-color 0.15s;
  }
  .input-row:focus-within { border-color: #3b82f640; }
  textarea.chat-input {
    flex: 1; background: transparent; border: none; outline: none;
    color: #e2e8f0; font-size: 13px; font-family: 'Inter', sans-serif;
    resize: none; min-height: 22px; max-height: 120px; line-height: 1.5;
    scrollbar-width: none;
  }
  textarea.chat-input::placeholder { color: #334155; }
  textarea.chat-input::-webkit-scrollbar { display: none; }
  .send-btn {
    width: 30px; height: 30px; border-radius: 8px; border: none;
    background: #3b82f6; color: white; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; flex-shrink: 0; transition: background 0.15s;
  }
  .send-btn:hover { background: #2563eb; }
  .send-btn:disabled { background: #1e293b; color: #334155; cursor: default; }
  .input-hint {
    font-size: 10px; color: #1f2937; margin-top: 6px; text-align: center;
  }

  /* ── Streamlit element overrides ── */
  [data-testid="stForm"],
  [data-testid="stTextInput"],
  [data-testid="stButton"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_input" not in st.session_state:
    st.session_state.pending_input = ""
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False

# ── Config ────────────────────────────────────────────────────────────────────
TABLEAU_URL  = st.secrets.get("TABLEAU_URL",  "https://public.tableau.com")
TABLEAU_VIEW = st.secrets.get("TABLEAU_VIEW", "")  # e.g. views/WorkbookName/SheetName
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")

VIEWS = [
    {"label": "전사 Summary",    "path": st.secrets.get("VIEW_SUMMARY",   TABLEAU_VIEW)},
    {"label": "유럽영업 BG",      "path": st.secrets.get("VIEW_EUROPE",    TABLEAU_VIEW)},
    {"label": "북미지역 BS",      "path": st.secrets.get("VIEW_NA",        TABLEAU_VIEW)},
    {"label": "해외영업 BS",      "path": st.secrets.get("VIEW_OVERSEAS",  TABLEAU_VIEW)},
    {"label": "한국지역 BS",      "path": st.secrets.get("VIEW_KOREA",     TABLEAU_VIEW)},
]

SUGGESTIONS = [
    "📈 영업이익 달성률은?",
    "💰 매출액 Plan vs Actual",
    "🌍 환율 영향 분석",
    "📦 원재료 차이 원인",
    "🏆 가장 성과 좋은 BG",
]

# ── Nav bar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="nav-bar">
  <div class="nav-logo">
    <div class="nav-logo-icon">📊</div>
    <div>
      <div class="nav-title">Tableau AI Assistant</div>
      <div class="nav-subtitle">P&amp;L 리포트 분석</div>
    </div>
  </div>
  <div class="nav-badge">Gemini 1.5 Flash + Tableau MCP</div>
</div>
""", unsafe_allow_html=True)

# ── Build current view URL from query param ───────────────────────────────────
params = st.query_params
active_idx = int(params.get("view", 0))
if active_idx >= len(VIEWS):
    active_idx = 0
current_view = VIEWS[active_idx]
tableau_full_url = f"{TABLEAU_URL.rstrip('/')}/{current_view['path'].lstrip('/')}"

# ── View tab buttons (above main grid) ───────────────────────────────────────
tab_html = '<div class="view-tabs">'
for i, v in enumerate(VIEWS):
    cls = "view-tab active" if i == active_idx else "view-tab"
    tab_html += f'<button class="{cls}" onclick="switchView({i})">{v["label"]}</button>'
tab_html += "</div>"

st.markdown(f"""
<script>
function switchView(idx) {{
  const url = new URL(window.location.href);
  url.searchParams.set('view', idx);
  window.location.href = url.toString();
}}
</script>
{tab_html}
""", unsafe_allow_html=True)

# ── AI Response generator ─────────────────────────────────────────────────────
def build_system_prompt():
    return """당신은 Tableau P&L 대시보드 전문 AI 어시스턴트입니다.
현재 분석 중인 대시보드: "2월 Consolidated P&L Report (연결손익보고)"

## 대시보드 주요 데이터 (2월 실적)
- 매출액: Plan 1,470억 / Actual 1,482억 / 차이 +13억 / 달성률 100.9%
- 수량: Plan 3,031천개 / Actual 2,950천개 / 차이 -82 / 달성률 97.3%
- 중량: Plan 30,302ton / Actual 30,378ton / 달성률 100.3%
- 판가(원/kg): Plan 4,850 / Actual 4,879 / 달성률 100.6%
- 매출원가: Plan 996억 / Actual 1,004억 / 달성률 100.8%
- 매출총이익: Plan 473억 / Actual 478억 / 달성률 101.1%
- 판매관리비: Plan 450억 / Actual 434억 / 달성률 96.4% (절감)
- 영업이익: Plan 23억 / Actual 44억 / 차이 +21억 / 달성률 191.8%
- 이익률: Plan 1.6% / Actual 3.0% / 달성률 190.2%

## 영업이익 차이 요인 분해 (워터폴 차트)
- 계획: +23억
- 환율 효과: +18억
- 원재료(단가): +1억
- 원재료(물량): -1억
- 매출(판가): -18억
- 매출(물량): +8억
- 가공비(변동비): -5억
- 가공비(고정비): +3억
- 판매비(변동비): -16억
- 실적: +44억 (내부차이 3억 + 외부차이 19억)

## 주요 이슈 컨텍스트
- 선임 상승에 따른 운반비 증가
- 환율 효과로 판가 달성 및 비용 미집행으로 영업이익 계획 초과 달성
- 탭 구성: 전사 Summary, 유럽영업BG, 북미지역BS, 해외영업BS, 한국지역BS, 중국지역BS, OE영업BG, 판가장

## 응답 가이드
- 한국어로 간결하고 명확하게 답변
- 숫자는 억원 단위로 표기, % 포함
- 주요 인사이트를 **굵게** 강조
- 필요 시 불릿으로 구조화
- 데이터 기반으로만 답변 (추측 시 명시)
"""

def stream_ai_response(user_msg: str):
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=build_system_prompt(),
    )
    # 대화 히스토리 구성 (Gemini 형식: user/model)
    history = []
    for m in st.session_state.messages[:-1]:
        role = "model" if m["role"] == "assistant" else "user"
        history.append({"role": role, "parts": [m["content"]]})

    chat = model.start_chat(history=history)
    response = chat.send_message(user_msg, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text

# ── Main layout HTML ──────────────────────────────────────────────────────────
# Build messages HTML
def render_messages():
    if not st.session_state.messages:
        return """
        <div style="flex:1; display:flex; flex-direction:column; align-items:center;
                    justify-content:center; gap:12px; color:#334155; padding:24px;">
          <div style="font-size:28px;">📊</div>
          <div style="font-size:14px; font-weight:500; color:#475569;">무엇이든 물어보세요</div>
          <div style="font-size:12px; text-align:center; line-height:1.8; color:#334155;">
            대시보드 수치, 달성률, 요인 분석,<br>BG별 실적 비교까지 답해드립니다
          </div>
        </div>"""

    html = ""
    for m in st.session_state.messages:
        role = m["role"]
        content = m["content"]
        # Basic markdown → html
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
        lines = content.split('\n')
        formatted = ""
        in_ul = False
        for line in lines:
            if line.startswith('- '):
                if not in_ul:
                    formatted += "<ul>"
                    in_ul = True
                formatted += f"<li>{line[2:]}</li>"
            else:
                if in_ul:
                    formatted += "</ul>"
                    in_ul = False
                if line.strip():
                    formatted += f"<p style='margin:0 0 4px;'>{line}</p>"
        if in_ul:
            formatted += "</ul>"

        if role == "user":
            html += f"""
            <div class="msg user">
              <div class="msg-avatar user">나</div>
              <div class="msg-bubble">{formatted}</div>
            </div>"""
        else:
            html += f"""
            <div class="msg ai">
              <div class="msg-avatar ai">AI</div>
              <div class="msg-bubble">{formatted}</div>
            </div>"""

    if st.session_state.is_loading:
        html += """
        <div class="msg ai">
          <div class="msg-avatar ai">AI</div>
          <div class="typing"><span></span><span></span><span></span></div>
        </div>"""
    return html

msgs_html = render_messages()

# Build suggestion chips
chips_html = "".join(
    f'<button class="chip" onclick="sendSuggestion(\'{s}\')">{s}</button>'
    for s in SUGGESTIONS
)

# ── Render full layout ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-grid">

  <!-- Tableau panel -->
  <div class="tableau-panel">
    <div class="panel-header">
      <div class="panel-header-title">2월 Consolidated P&amp;L Report</div>
      <div style="font-size:11px;color:#334155;">{current_view['label']}</div>
    </div>
    <div class="tableau-wrapper">
      <tableau-viz
        id="tableauViz"
        src="{tableau_full_url}"
        toolbar="hidden"
        hide-tabs="true"
      ></tableau-viz>
    </div>
  </div>

  <!-- Chat panel -->
  <div class="chat-panel">
    <div class="chat-header">
      <div class="chat-header-title">🤖 AI 분석 어시스턴트</div>
      <div class="chat-header-desc">P&amp;L 데이터에 대해 자유롭게 질문하세요</div>
    </div>

    <div class="chips-wrap">{chips_html}</div>

    <div class="messages-scroll" id="msgScroll">{msgs_html}</div>

    <div class="input-area">
      <div class="input-row">
        <textarea
          id="chatInput"
          class="chat-input"
          rows="1"
          placeholder="질문을 입력하세요... (Shift+Enter 줄바꿈)"
        ></textarea>
        <button class="send-btn" id="sendBtn" onclick="submitChat()">↑</button>
      </div>
      <div class="input-hint">Gemini 1.5 Flash powered · Tableau MCP connected</div>
    </div>
  </div>

</div>

<script>
// ── Auto-scroll to bottom ──
const scroll = document.getElementById('msgScroll');
if (scroll) scroll.scrollTop = scroll.scrollHeight;

// ── Auto-resize textarea ──
const ta = document.getElementById('chatInput');
if (ta) {{
  ta.addEventListener('input', () => {{
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }});
  ta.addEventListener('keydown', (e) => {{
    if (e.key === 'Enter' && !e.shiftKey) {{
      e.preventDefault();
      submitChat();
    }}
  }});
  // Restore pending input
  const pending = sessionStorage.getItem('pendingInput');
  if (pending) {{ ta.value = pending; sessionStorage.removeItem('pendingInput'); }}
}}

// ── Submit chat ──
function submitChat() {{
  const input = document.getElementById('chatInput');
  const msg = input ? input.value.trim() : '';
  if (!msg) return;
  // Store in sessionStorage → Streamlit picks it up via URL param trick
  sessionStorage.setItem('chatMsg', msg);
  const url = new URL(window.location.href);
  url.searchParams.set('msg', encodeURIComponent(msg));
  url.searchParams.set('ts', Date.now());
  window.location.href = url.toString();
}}

// ── Suggestion chip ──
function sendSuggestion(text) {{
  const url = new URL(window.location.href);
  url.searchParams.set('msg', encodeURIComponent(text));
  url.searchParams.set('ts', Date.now());
  window.location.href = url.toString();
}}
</script>
""", unsafe_allow_html=True)

# ── Process incoming message from URL param ───────────────────────────────────
incoming = params.get("msg", "")
if incoming and not st.session_state.is_loading:
    # Avoid reprocessing same message (check last user msg)
    last_user = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        None
    )
    if incoming != last_user:
        st.session_state.messages.append({"role": "user", "content": incoming})
        st.session_state.is_loading = True

        # Clear msg param and rerun to show loading state
        new_params = dict(params)
        new_params.pop("msg", None)
        new_params.pop("ts", None)
        st.query_params.update(new_params)
        st.rerun()

# ── Generate AI response if loading ──────────────────────────────────────────
if st.session_state.is_loading:
    last_user_msg = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        ""
    )
    if last_user_msg:
        full_response = ""
        for chunk in stream_ai_response(last_user_msg):
            full_response += chunk
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.session_state.is_loading = False
    st.rerun()
