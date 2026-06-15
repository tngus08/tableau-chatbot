# 📊 Tableau AI Assistant

Tableau Cloud 대시보드에 Claude AI 챗봇을 결합한 Streamlit 웹 애플리케이션입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| **Tableau 임베드** | Embedding API v3로 대시보드 직접 렌더링 |
| **AI 챗봇** | Claude Sonnet 4.6 기반 P&L 데이터 질의응답 |
| **Tableau MCP 연동** | PAT 인증으로 실시간 데이터 컨텍스트 주입 |
| **탭 전환** | 사업부별 뷰 전환 (전사, 유럽, 북미, 해외 등) |
| **추천 질문** | 빠른 질문 칩 제공 |

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Cloud                        │
│                                                         │
│   ┌─────────────────────┐   ┌─────────────────────┐    │
│   │   Tableau Panel      │   │    Chat Panel        │    │
│   │                      │   │                      │    │
│   │  Embedding API v3    │   │  Claude Sonnet 4.6   │    │
│   │  (iframe + JS SDK)   │   │  + Tableau MCP       │    │
│   │                      │   │  컨텍스트 주입        │    │
│   └─────────────────────┘   └─────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  Tableau Cloud                  Anthropic API
  (REST API + Embed)             (claude-sonnet-4-6)
```

## 로컬 실행

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 시크릿 설정 (.streamlit/secrets.toml 편집)
cp .streamlit/secrets.toml .streamlit/secrets.local.toml
# → secrets.toml 파일에 실제 값 입력

# 3. 실행
streamlit run app.py
```

## Streamlit Cloud 배포

### 1. GitHub 리포지토리 생성
```bash
git init
git add .
git commit -m "init: Tableau AI Assistant"
git remote add origin https://github.com/your-id/tableau-chatbot.git
git push -u origin main
```

### 2. Streamlit Cloud 연결
1. https://share.streamlit.io 접속
2. **New app** → GitHub 리포 선택
3. Main file: `app.py`
4. **Advanced settings → Secrets** 에 아래 항목 입력

### 3. Secrets 설정 (Streamlit Cloud)
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
TABLEAU_SERVER    = "https://prod-apnortheast-a.online.tableau.com"
TABLEAU_SITE      = "your-site"
TABLEAU_PAT_NAME  = "token-name"
TABLEAU_PAT_VALUE = "token-value"
TABLEAU_URL       = "https://prod-apnortheast-a.online.tableau.com"
TABLEAU_VIEW      = "views/WorkbookName/ViewName"
VIEW_SUMMARY      = "views/WorkbookName/Summary"
VIEW_EUROPE       = "views/WorkbookName/Europe"
VIEW_NA           = "views/WorkbookName/NorthAmerica"
VIEW_OVERSEAS     = "views/WorkbookName/Overseas"
VIEW_KOREA        = "views/WorkbookName/Korea"
```

## Tableau PAT 생성 방법

1. Tableau Cloud 로그인
2. 우상단 프로필 아이콘 → **내 계정 설정**
3. **Personal Access Tokens** 섹션 → **새 토큰 만들기**
4. 토큰 이름과 값을 secrets.toml에 입력

## Tableau 뷰 URL 확인 방법

Tableau Cloud에서 임베드할 뷰를 열고 URL 확인:
```
https://prod-apnortheast-a.online.tableau.com/#/site/mysite/views/MyWorkbook/MyView
                                                                   ↑ 이 부분을 TABLEAU_VIEW에 입력
→ TABLEAU_VIEW = "views/MyWorkbook/MyView"
```

## 파일 구조

```
tableau-chatbot/
├── app.py              # 메인 Streamlit 앱
├── tableau_mcp.py      # Tableau API 헬퍼
├── requirements.txt    # 패키지 의존성
├── README.md           # 이 파일
└── .streamlit/
    └── secrets.toml    # 시크릿 설정 (Git에 올리지 말 것!)
```

## .gitignore

```
.streamlit/secrets.toml
.streamlit/secrets.local.toml
__pycache__/
*.pyc
.env
```

## 주의사항

- `secrets.toml`은 절대 GitHub에 커밋하지 마세요
- Tableau Embedding API는 Tableau Cloud의 **임베드 허용** 설정이 필요합니다
- Tableau Cloud 관리자 → 사이트 설정 → **임베딩** 탭에서 허용 도메인 추가
