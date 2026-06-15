import streamlit as st
import streamlit.components.v1 as components
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

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  [data-testid="stAppViewContainer"] { background: #0f1117; }
  [data-testid="stHeader"] { display: none; }
  [data-testid="stToolbar"] { display: none; }
  section[data-testid="stMain"] > div { padding: 0 !important; }
  [data-testid="stVerticalBlock"] { gap: 0 !important; padding: 0 !important; }
  * { font-family: 'Inter', sans-serif; box-sizing: border-box; }

  .nav-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 24px; background: #161b27;
    border-bottom: 1px solid #1f2937;
  }
  .nav-left { display: flex; align-items: center; gap: 10px; }
  .nav-icon {
    width: 30px; height: 30px; background: #3b82f6;
    border-radius: 7px; display: flex; align-items: center;
    justify-content: center; font-size: 15px;
  }
  .nav-title { font-size: 14px; font-weight: 600; color: #f1f5f9; }
  .nav-sub { font-size: 11px; color: #64748b; }
  .nav-badge {
    font-size: 11px; padding: 3px 10px;
    background: #1e293b; border: 1px solid #334155;
    border-radius: 20px; color: #94a3b8;
  }

  .tabs-bar {
    display: flex; gap: 6px; padding: 8px 16px;
    background: #0f1117; border-bottom: 1px solid #1f2937;
    overflow-x: auto;
  }
  .tabs-bar::-webkit-scrollbar { display: none; }

  .layout {
    display: grid; grid-template-columns: 1fr 380px;
    height: calc(100vh - 94px); overflow: hidden;
  }
  .tableau-panel {
    background: #0f1117; border-right: 1px solid #1f2937;
    padding: 14px; overflow: hidden;
    display: flex; align-items: stretch;
  }
  tableau-viz { width: 100%; height: 100%; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False

# ── Config ────────────────────────────────────────────────────────────────────
TABLEAU_URL  = st.secrets.get("TABLEAU_URL",  "https://public.tableau.com")
TABLEAU_VIEW = st.secrets.get("TABLEAU_VIEW", "")
GEMINI_KEY   = st.secrets.get("GEMINI_API_KEY", "")

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
params = st.query_params
active_idx = int(params.get("view", 0))
if active_idx >= len(VIEWS):
    active_idx = 0
current_view = VIEWS[active_idx]
tableau_full_url = f"{TABLEAU_URL.rstrip('/')}/{current_view['path'].lstrip('/')}"

# ── Nav bar ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="nav-bar">
  <div class="nav-left">
    <div class="nav-icon">&#128202;</div>
    <div>
      <div class="nav-title">Tableau AI Assistant</div>
      <div class="nav-sub">P&amp;L 리포트 분석</div>
    </div>
  </div>
  <div class="nav-badge">Gemini 1.5 Flash + Tableau MCP</div>
</div>
""", unsafe_allow_html=True)

# ── Tab bar ───────────────────────────────────────────────────────────────────
tab_btns = ""
for i, v in enumerate(VIEWS):
    active_style = "color:#3b82f6;border-color:#3b82f640;background:#3b82f610;" if i == active_idx else "color:#64748b;border-color:#1f2937;background:transparent;"
    tab_btns += f"""<button onclick="location.href=location.pathname+'?view={i}'"
      style="font-size:12px;font-weight:500;padding:5px 13px;border-radius:6px;
             border:1px solid;cursor:pointer;white-space:nowrap;{active_style}"
    >{v['label']}</button>"""

st.markdown(f'<div class="tabs-bar">{tab_btns}</div>', unsafe_allow_html=True)

# ── AI helpers ────────────────────────────────────────────────────────────────
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

## 영업이익 차이 요인 분해 (워터폴)
- 계획 23억 → 환율+18 / 원재료단가+1 / 원재료물량-1 / 매출판가-18 / 매출물량+8 / 가공비변동-5 / 가공비고정+3 / 판매비변동-16 → 실적 44억

## 응답 가이드
- 한국어로 간결하게 답변
- 숫자는 억원 단위, % 포함
- 데이터 기반으로만 답변
"""

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
    response = chat.send_message(user_msg)
    return response.text

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

# ── Build chat HTML ───────────────────────────────────────────────────────────
def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

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

# Messages HTML
if not st.session_state.messages:
    msgs_html = """
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;height:100%;gap:10px;color:#475569;padding:20px;">
      <div style="font-size:26px;">&#128202;</div>
      <div style="font-size:13px;font-weight:500;color:#64748b;">무엇이든 물어보세요</div>
      <div style="font-size:11px;text-align:center;line-height:1.8;color:#334155;">
        대시보드 수치, 달성률, 요인 분석<br>BG별 실적 비교까지 답해드립니다
      </div>
    </div>"""
else:
    msgs_html = ""
    for m in st.session_state.messages:
        content = md_to_html(m["content"])
        if m["role"] == "user":
            msgs_html += f"""
            <div style="display:flex;flex-direction:row-reverse;gap:8px;align-items:flex-start;margin-bottom:10px;">
              <div style="width:26px;height:26px;border-radius:7px;background:#1e293b;border:1px solid #334155;
                          display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;
                          color:#94a3b8;flex-shrink:0;">나</div>
              <div style="max-width:80%;padding:9px 12px;border-radius:11px;border-bottom-right-radius:3px;
                          background:#1d3461;border:1px solid #2d4a7a;font-size:12px;line-height:1.6;color:#bfdbfe;">
                {content}</div>
            </div>"""
        else:
            msgs_html += f"""
            <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:10px;">
              <div style="width:26px;height:26px;border-radius:7px;background:#3b82f6;
                          display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;
                          color:white;flex-shrink:0;">AI</div>
              <div style="max-width:80%;padding:9px 12px;border-radius:11px;border-bottom-left-radius:3px;
                          background:#161b27;border:1px solid #1f2937;font-size:12px;line-height:1.6;color:#e2e8f0;">
                {content}</div>
            </div>"""

# Chips HTML
chips_html = ""
for s in SUGGESTIONS:
    chips_html += f"""<button onclick="sendMsg('{s}')"
      style="font-size:11px;padding:4px 11px;background:#1e293b;border:1px solid #1f2937;
             border-radius:20px;color:#64748b;cursor:pointer;white-space:nowrap;">
      {s}</button>"""

# Full chat component HTML
chat_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }}
  body {{ background:#0f1117; height:100vh; display:flex; flex-direction:column; overflow:hidden; }}

  .chat-header {{
    padding:12px 16px; background:#161b27; border-bottom:1px solid #1f2937; flex-shrink:0;
  }}
  .chat-header-title {{ font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:3px; }}
  .chat-header-sub {{ font-size:11px;color:#475569; }}

  .chips {{
    display:flex;flex-wrap:wrap;gap:5px;padding:8px 12px;
    border-bottom:1px solid #1f2937;flex-shrink:0;background:#0f1117;
  }}
  .chips button:hover {{ color:#3b82f6 !important; border-color:#3b82f640 !important; background:#3b82f610 !important; }}

  .messages {{
    flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;
    scrollbar-width:thin;scrollbar-color:#1f2937 transparent;
  }}
  .messages::-webkit-scrollbar {{ width:3px; }}
  .messages::-webkit-scrollbar-thumb {{ background:#1f2937;border-radius:3px; }}
  .messages p {{ margin:0 0 4px; }}
  .messages ul {{ margin:4px 0 4px 14px; }}
  .messages li {{ margin-bottom:3px;color:#cbd5e1; }}
  .messages strong {{ color:#60a5fa; }}
  .messages code {{ font-size:11px;background:#0f1117;padding:1px 4px;border-radius:3px;color:#7dd3fc; }}

  .input-area {{
    padding:10px 12px 12px;background:#0f1117;border-top:1px solid #1f2937;flex-shrink:0;
  }}
  .input-row {{
    display:flex;gap:6px;align-items:flex-end;
    background:#161b27;border:1px solid #1f2937;border-radius:10px;padding:8px 10px;
  }}
  .input-row:focus-within {{ border-color:#3b82f640; }}
  textarea {{
    flex:1;background:transparent;border:none;outline:none;
    color:#e2e8f0;font-size:12px;font-family:'Inter',sans-serif;
    resize:none;min-height:20px;max-height:100px;line-height:1.5;
    scrollbar-width:none;
  }}
  textarea::placeholder {{ color:#334155; }}
  button.send {{
    width:28px;height:28px;border-radius:7px;border:none;
    background:#3b82f6;color:white;cursor:pointer;font-size:14px;flex-shrink:0;
  }}
  button.send:hover {{ background:#2563eb; }}
  .hint {{ font-size:10px;color:#1f2937;margin-top:5px;text-align:center; }}
</style>
</head>
<body>

<div class="chat-header">
  <div class="chat-header-title">&#129302; AI 분석 어시스턴트</div>
  <div class="chat-header-sub">P&amp;L 데이터에 대해 자유롭게 질문하세요</div>
</div>

<div class="chips">{chips_html}</div>

<div class="messages" id="msgs">{msgs_html}</div>

<div class="input-area">
  <div class="input-row">
    <textarea id="inp" rows="1" placeholder="질문을 입력하세요... (Enter 전송)"></textarea>
    <button class="send" onclick="send()">&#8593;</button>
  </div>
  <div class="hint">Gemini 1.5 Flash powered · Tableau MCP connected</div>
</div>

<script>
const msgs = document.getElementById('msgs');
if (msgs) msgs.scrollTop = msgs.scrollHeight;

const ta = document.getElementById('inp');
if (ta) {{
  ta.addEventListener('input', () => {{
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 100) + 'px';
  }});
  ta.addEventListener('keydown', e => {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); send(); }}
  }});
}}

function sendMsg(text) {{
  const url = new URL(window.parent.location.href);
  url.searchParams.set('msg', encodeURIComponent(text));
  url.searchParams.set('ts', Date.now());
  window.parent.location.href = url.toString();
}}

function send() {{
  const msg = ta ? ta.value.trim() : '';
  if (!msg) return;
  sendMsg(msg);
}}
</script>
</body>
</html>"""

# ── Render layout ─────────────────────────────────────────────────────────────
st.markdown(f"""
<script type="module" src="https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js"></script>
<div class="layout">
  <div class="tableau-panel">
    <tableau-viz id="tableauViz" src="{tableau_full_url}" toolbar="hidden" hide-tabs="true"></tableau-viz>
  </div>
</div>
""", unsafe_allow_html=True)

# Chat panel via component (avoids markdown parsing issues)
components.html(chat_html, height=600, scrolling=False)