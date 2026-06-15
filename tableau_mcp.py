"""
tableau_mcp.py
Tableau REST API / MCP 연동 헬퍼

Streamlit secrets에서 자격증명을 읽고,
대시보드 컨텍스트 데이터를 AI 챗봇에 제공합니다.
"""

from __future__ import annotations
import os
import requests
import streamlit as st
from functools import lru_cache


# ── Credentials ───────────────────────────────────────────────────────────────
def _get_secret(key: str, fallback: str = "") -> str:
    try:
        return st.secrets.get(key, os.environ.get(key, fallback))
    except Exception:
        return os.environ.get(key, fallback)

TABLEAU_SERVER  = _get_secret("TABLEAU_SERVER",  "https://prod-apnortheast-a.online.tableau.com")
TABLEAU_SITE    = _get_secret("TABLEAU_SITE",    "")
TABLEAU_PAT_NAME  = _get_secret("TABLEAU_PAT_NAME",  "")
TABLEAU_PAT_VALUE = _get_secret("TABLEAU_PAT_VALUE", "")


# ── Auth ──────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _auth_token() -> tuple[str, str]:
    """PAT로 인증 후 (token, siteId) 반환. 결과를 캐시."""
    if not (TABLEAU_PAT_NAME and TABLEAU_PAT_VALUE):
        return "", ""

    url = f"{TABLEAU_SERVER}/api/3.21/auth/signin"
    payload = {
        "credentials": {
            "personalAccessTokenName": TABLEAU_PAT_NAME,
            "personalAccessTokenSecret": TABLEAU_PAT_VALUE,
            "site": {"contentUrl": TABLEAU_SITE},
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        creds = r.json()["credentials"]
        return creds["token"], creds["site"]["id"]
    except Exception as e:
        return "", ""


# ── Public helpers ────────────────────────────────────────────────────────────
def get_tableau_context() -> dict:
    """
    챗봇 시스템 프롬프트용 컨텍스트 딕셔너리 반환.
    API 연결이 없으면 하드코딩된 2월 P&L 데이터를 반환.
    """
    token, site_id = _auth_token()
    if token:
        # 실제 API에서 데이터를 가져오는 경우
        return _fetch_live_context(token, site_id)
    # Fallback: 대시보드 스냅샷 기반 컨텍스트
    return _static_feb_context()


def fetch_view_data(view_id: str) -> list[dict]:
    """특정 뷰의 CSV 데이터를 파싱하여 반환."""
    token, site_id = _auth_token()
    if not token:
        return []
    url = f"{TABLEAU_SERVER}/api/3.21/sites/{site_id}/views/{view_id}/data"
    headers = {"x-tableau-auth": token}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return []
        keys = [k.strip() for k in lines[0].split(",")]
        return [
            dict(zip(keys, [v.strip() for v in line.split(",")]))
            for line in lines[1:]
        ]
    except Exception:
        return []


def search_tableau_content(query: str, content_types: list[str] | None = None) -> list[dict]:
    """Tableau 콘텐츠 검색. content_types 예: ['workbook', 'datasource']"""
    token, site_id = _auth_token()
    if not token:
        return []
    types = content_types or ["workbook", "datasource", "view"]
    url = f"{TABLEAU_SERVER}/api/3.21/sites/{site_id}/search"
    headers = {"x-tableau-auth": token, "Content-Type": "application/json"}
    payload = {
        "terms": query,
        "filter": {"contentTypes": types},
        "limit": 10,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        return [
            {
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "id": item.get("luid", ""),
                "project": item.get("projectName", ""),
                "views": item.get("totalViewCount", 0),
            }
            for item in results
        ]
    except Exception:
        return []


# ── Private helpers ───────────────────────────────────────────────────────────
def _fetch_live_context(token: str, site_id: str) -> dict:
    """실제 Tableau API 호출로 컨텍스트 구성."""
    headers = {"x-tableau-auth": token}
    base = f"{TABLEAU_SERVER}/api/3.21/sites/{site_id}"
    ctx: dict = {"source": "live"}
    try:
        r = requests.get(f"{base}/datasources?pageSize=5", headers=headers, timeout=10)
        if r.ok:
            ds = r.json().get("datasources", {}).get("datasource", [])
            ctx["datasources"] = [
                {"name": d.get("name"), "type": d.get("type"), "project": d.get("project", {}).get("name")}
                for d in ds
            ]
    except Exception:
        pass
    # Merge static financial data (always available)
    ctx.update(_static_feb_context())
    ctx["source"] = "live+static"
    return ctx


def _static_feb_context() -> dict:
    """2월 P&L 스냅샷 데이터 (API 불필요)."""
    return {
        "source": "static",
        "report": "2월 Consolidated P&L Report",
        "period": "2025년 2월",
        "kpis": {
            "매출액_억원":    {"plan": 1470, "actual": 1482, "diff": 13,  "rate": 100.9},
            "수량_천개":      {"plan": 3031, "actual": 2950, "diff": -82, "rate": 97.3},
            "중량_ton":       {"plan": 30302,"actual": 30378,"diff": 76,  "rate": 100.3},
            "판가_원/kg":     {"plan": 4850, "actual": 4879, "diff": 29,  "rate": 100.6},
            "매출원가_억원":  {"plan": 996,  "actual": 1004, "diff": 8,   "rate": 100.8},
            "원가율_pct":     {"plan": 67.8, "actual": 67.7, "diff": -0.1,"rate": 99.9},
            "매출총이익_억원":{"plan": 473,  "actual": 478,  "diff": 5,   "rate": 101.1},
            "판매관리비_억원":{"plan": 450,  "actual": 434,  "diff": -16, "rate": 96.4},
            "영업이익_억원":  {"plan": 23,   "actual": 44,   "diff": 21,  "rate": 191.8},
            "이익률_pct":     {"plan": 1.6,  "actual": 3.0,  "diff": 1.4, "rate": 190.2},
        },
        "waterfall_억원": {
            "계획":         23,
            "환율":        +18,
            "원재료_단가": +1,
            "원재료_물량": -1,
            "매출_판가":   -18,
            "매출_물량":   +8,
            "가공비_변동": -5,
            "가공비_고정": +3,
            "판매비_변동": -16,
            "실적":         44,
        },
        "gap_분해": {
            "영업이익_차이": 21,
            "내부차이":       3,
            "외부차이":      19,
        },
        "주요이슈": [
            "선임 상승에 따른 운반비 증가",
            "환율 효과로 판가 달성 및 비용 미집행 → 영업이익 계획 초과 달성",
            "수량은 계획 대비 -82천개 미달 (97.3%)",
        ],
        "tabs": ["전사 Summary","유럽영업BG","북미지역BS","해외영업BS","한국지역BS","중국지역BS","OE영업BG","판가장"],
    }
