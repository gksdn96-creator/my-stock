import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime
import time

st.set_page_config(
    page_title="AI 반도체 주식 분석",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 AI 반도체 주식 전문 분석")
st.caption("NVIDIA, AMD, TSMC 등 AI 반도체 밸류체인 핵심 기업 심층 분석 대시보드")

# ----------------------------
# 세션 (Yahoo 차단 회피)
# ----------------------------
@st.cache_resource
def get_session():
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate="chrome")
    except Exception:
        return None

SESSION = get_session()

# ----------------------------
# AI 반도체 밸류체인 종목 리스트
# ----------------------------
AI_CHIP_TICKERS = {
    "NVIDIA (GPU/AI가속기)": "NVDA",
    "AMD (GPU/CPU)": "AMD",
    "TSMC (파운드리)": "TSM",
    "Broadcom (커스텀칩/네트워킹)": "AVGO",
    "Intel (CPU/파운드리)": "INTC",
    "Qualcomm (모바일AP)": "QCOM",
    "ASML (노광장비)": "ASML",
    "Micron (HBM/메모리)": "MU",
    "SK하이닉스 (HBM/메모리)": "000660.KS",
    "삼성전자 (메모리/파운드리)": "005930.KS",
    "Arm Holdings (설계IP)": "ARM",
    "Marvell (데이터센터칩)": "MRVL",
}

# ----------------------------
# 사이드바 설정
# ----------------------------
st.sidebar.header("⚙️ 분석 설정")

selected_names = st.sidebar.multiselect(
    "분석할 AI 반도체 기업",
    options=list(AI_CHIP_TICKERS.keys()),
    default=["NVIDIA (GPU/AI가속기)", "AMD (GPU/CPU)", "TSMC (파운드리)",
             "Broadcom (커스텀칩/네트워킹)", "SK하이닉스 (HBM/메모리)"]
)

period_options = {
    "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y", "5년": "5y"
}
period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=2)
period = period_options[period_label]

st.sidebar.markdown("---")
if st.sidebar.button("🔄 캐시 초기화"):
    st.cache_data.clear()
    st.rerun()

if not selected_names:
    st.warning("사이드바에서 기업을 최소 2개 이상 선택해주세요.")
    st.stop()

if len(selected_names) < 2:
    st.info("비교 분석을 위해 2개 이상의 기업을 선택하는 것을 권장합니다.")

tickers = [AI_CHIP_TICKERS[n] for n in selected_names]
name_map = {AI_CHIP_TICKERS[n]: n for n in selected_names}

# ----------------------------
# 데이터 로딩 함수 (재시도 포함)
# ----------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def load_history(ticker, period, retries=3):
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker, session=SESSION)
            df = t.history(period=period)
            if not df.empty:
                return df
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def load_fundamentals(ticker, retries=3):
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker, session=SESSION)
            info = t.get_info()
            return info
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return {}

def safe_get(d, key, default=None):
    val = d.get(key, default)
    return val if val is not None else default

# ----------------------------
# 데이터 수집
# ----------------------------
with st.spinner("데이터를 불러오는 중입니다..."):
    history_data = {}
    fundamental_data = {}
    for ticker in tickers:
        history_data[ticker] = load_history(ticker, period)
        fundamental_data[ticker] = load_fundamentals(ticker)

valid_tickers = [t for t in tickers if not history_data[t].empty]

if not valid_tickers:
    st.error("데이터를 불러올 수 없습니다. Yahoo Finance 요청 제한일 수 있으니 잠시 후 다시 시도해주세요.")
    st.stop()

# ============================================================
# 1. 핵심 지표 요약 카드
# ============================================================
st.header("📊 핵심 지표 요약")

cols = st.columns(len(valid_tickers))
for i, ticker in enumerate(valid_tickers):
    df = history_data[ticker]
    info = fundamental_data[ticker]
    name = name_map[ticker]

    last_price = df["Close"].iloc[-1]
    prev_price = df["Close"].iloc[-2] if len(df) > 1 else last_price
    change_pct = (last_price - prev_price) / prev_price * 100

    with cols[i]:
        st.metric(
            label=name.split(" (")[0],
            value=f"{last_price:,.2f}",
            delta=f"{change_pct:.2f}%"
        )
        market_cap = safe_get(info, "marketCap")
        if market_cap:
            st.caption(f"시가총액: ${market_cap/1e9:,.1f}B")
        per = safe_get(info, "trailingPE")
        if per:
            st.caption(f"PER: {per:.1f}배")

st.markdown("---")

# ============================================================
# 2. 주가 수익률 비교 (정규화)
# ============================================================
st.header("📈 주가 수익률 비교")
st.caption(f"최근 {period_label} 기준, 시작일 대비 수익률(%)")

fig_compare = go.Figure()
for ticker in valid_tickers:
    df = history_data[ticker]
    normalized = (df["Close"] / df["Close"].iloc[0] - 1) * 100
    fig_compare.add_trace(
        go.Scatter(x=df.index, y=normalized, mode="lines",
                   name=name_map[ticker].split(" (")[0], line=dict(width=2))
    )

fig_compare.update_layout(
    height=500,
    yaxis_title="수익률 (%)",
    template="plotly_white",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_compare, use_container_width=True)

st.markdown("---")

# ============================================================
# 3. 밸류에이션 비교 (PER, PBR, 매출성장률 등)
# ============================================================
st.header("💰 밸류에이션 & 재무 비교")

valuation_rows = []
for ticker in valid_tickers:
    info = fundamental_data[ticker]
    valuation_rows.append({
        "기업": name_map[ticker].split(" (")[0],
        "시가총액($B)": round(safe_get(info, "marketCap", 0) / 1e9, 1) if safe_get(info, "marketCap") else None,
        "PER": round(safe_get(info, "trailingPE"), 1) if safe_get(info, "trailingPE") else None,
        "Forward PER": round(safe_get(info, "forwardPE"), 1) if safe_get(info, "forwardPE") else None,
        "PBR": round(safe_get(info, "priceToBook"), 1) if safe_get(info, "priceToBook") else None,
        "매출성장률(%)": round(safe_get(info, "revenueGrowth", 0) * 100, 1) if safe_get(info, "revenueGrowth") else None,
        "영업이익률(%)": round(safe_get(info, "operatingMargins", 0) * 100, 1) if safe_get(info, "operatingMargins") else None,
        "ROE(%)": round(safe_get(info, "returnOnEquity", 0) * 100, 1) if safe_get(info, "returnOnEquity") else None,
        "배당수익률(%)": round(safe_get(info, "dividendYield", 0) * 100, 2) if safe_get(info, "dividendYield") else 0,
    })

valuation_df = pd.DataFrame(valuation_rows).set_index("기업")
st.dataframe(valuation_df, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("시가총액 비교")
    mc_df = valuation_df.reset_index().dropna(subset=["시가총액($B)"])
    if not mc_df.empty:
        fig_mc = px.bar(mc_df, x="기업", y="시가총액($B)", color="기업",
                        template="plotly_white")
        fig_mc.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_mc, use_container_width=True)

with col2:
    st.subheader("PER 비교 (밸류에이션 부담도)")
    per_df = valuation_df.reset_index().dropna(subset=["PER"])
    if not per_df.empty:
        fig_per = px.bar(per_df, x="기업", y="PER", color="기업",
                         template="plotly_white")
        fig_per.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_per, use_container_width=True)

st.markdown("---")

# ============================================================
# 4. 수익성 vs 성장성 산점도
# ============================================================
st.header("🎯 성장성 vs 수익성 매트릭스")
st.caption("우상단에 위치할수록 '고성장 + 고수익성' 기업입니다")

scatter_df = valuation_df.reset_index().dropna(subset=["매출성장률(%)", "영업이익률(%)"])
if not scatter_df.empty:
    fig_scatter = px.scatter(
        scatter_df, x="매출성장률(%)", y="영업이익률(%)",
        size="시가총액($B)", color="기업", text="기업",
        template="plotly_white", size_max=60
    )
    fig_scatter.update_traces(textposition="top center")
    fig_scatter.update_layout(height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.info("일부 기업의 재무 데이터가 부족하여 매트릭스를 표시할 수 없습니다.")

st.markdown("---")

# ============================================================
# 5. 변동성 & 상관관계 분석
# ============================================================
st.header("📉 리스크 & 상관관계 분석")

col1, col2 = st.columns(2)

# 변동성 (연환산 표준편차)
volatility_rows = []
returns_data = {}
for ticker in valid_tickers:
    df = history_data[ticker]
    daily_returns = df["Close"].pct_change().dropna()
    returns_data[ticker] = daily_returns
    annual_vol = daily_returns.std() * np.sqrt(252) * 100
    volatility_rows.append({"기업": name_map[ticker].split(" (")[0], "연변동성(%)": round(annual_vol, 1)})

with col1:
    st.subheader("연간 변동성 (리스크)")
    vol_df = pd.DataFrame(volatility_rows)
    fig_vol = px.bar(vol_df, x="기업", y="연변동성(%)", color="기업",
                     template="plotly_white")
    fig_vol.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig_vol, use_container_width=True)

with col2:
    st.subheader("종목 간 상관관계")
    if len(valid_tickers) >= 2:
        returns_df = pd.DataFrame({
            name_map[t].split(" (")[0]: returns_data[t] for t in valid_tickers
        }).dropna()
        corr_matrix = returns_df.corr()
        fig_corr = px.imshow(
            corr_matrix, text_auto=".2f", color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1, template="plotly_white"
        )
        fig_corr.update_layout(height=400)
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("상관관계 분석은 2개 이상 종목 선택 시 가능합니다.")

st.markdown("---")

# ============================================================
# 6. 개별 종목 상세 캔들차트
# ============================================================
st.header("🕯️ 개별 종목 상세 차트")

tab_names = [name_map[t].split(" (")[0] for t in valid_tickers]
tabs = st.tabs(tab_names)

for tab, ticker in zip(tabs, valid_tickers):
    with tab:
        df = history_data[ticker].copy()
        info = fundamental_data[ticker]

        # 기업 개요
        st.markdown(f"**{name_map[ticker]}** ({ticker})")
        sector = safe_get(info, "sector", "N/A")
        industry = safe_get(info, "industry", "N/A")
        st.caption(f"섹터: {sector} | 산업: {industry}")

        summary = safe_get(info, "longBusinessSummary")
        if summary:
            with st.expander("기업 개요 보기"):
                st.write(summary)

        # 캔들차트
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA60"] = df["Close"].rolling(60).mean()

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.05, row_heights=[0.7, 0.3]
        )
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="가격",
            increasing_line_color="red", decreasing_line_color="blue"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="20일선",
                                  line=dict(color="orange", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA60"], name="60일선",
                                  line=dict(color="purple", width=1)), row=1, col=1)

        vol_colors = ["red" if r["Close"] >= r["Open"] else "blue" for _, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량",
                             marker_color=vol_colors), row=2, col=1)

        fig.update_layout(
            height=550, xaxis_rangeslider_visible=False,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        # 상세 재무 지표
        st.subheader("주요 재무 지표")
        metric_cols = st.columns(4)
        metrics = [
            ("52주 최고", safe_get(info, "fiftyTwoWeekHigh")),
            ("52주 최저", safe_get(info, "fiftyTwoWeekLow")),
            ("평균 거래량", safe_get(info, "averageVolume")),
            ("베타", safe_get(info, "beta")),
        ]
        for col, (label, val) in zip(metric_cols, metrics):
            if val is not None:
                if label == "평균 거래량":
                    col.metric(label, f"{val:,.0f}")
                else:
                    col.metric(label, f"{val:,.2f}")
            else:
                col.metric(label, "N/A")

st.markdown("---")
st.caption(f"⚠️ 본 대시보드는 투자 참고용이며 투자 조언이 아닙니다. 데이터 출처: Yahoo Finance | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
