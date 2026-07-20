import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

# ----------------------------
# 페이지 기본 설정
# ----------------------------
st.set_page_config(
    page_title="글로벌 주요 주식 대시보드",
    page_icon="📈",
    layout="wide"
)

st.title("📈 글로벌 주요 주식 대시보드")
st.caption("Yahoo Finance (yfinance) 데이터를 기반으로 제작되었습니다.")

# ----------------------------
# Yahoo 차단 회피용 세션 (curl_cffi로 브라우저처럼 위장)
# ----------------------------
@st.cache_resource
def get_session():
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome")
        return session
    except Exception:
        return None

SESSION = get_session()

# ----------------------------
# 주요 종목 리스트
# ----------------------------
TICKERS = {
    "🇺🇸 Apple": "AAPL",
    "🇺🇸 Microsoft": "MSFT",
    "🇺🇸 NVIDIA": "NVDA",
    "🇺🇸 Amazon": "AMZN",
    "🇺🇸 Alphabet(Google)": "GOOGL",
    "🇺🇸 Tesla": "TSLA",
    "🇺🇸 Meta": "META",
    "🇰🇷 삼성전자": "005930.KS",
    "🇰🇷 SK하이닉스": "000660.KS",
    "🇯🇵 도요타": "7203.T",
    "🇹🇼 TSMC": "TSM",
    "🇨🇳 알리바바": "BABA",
    "🇩🇪 SAP": "SAP",
}

# ----------------------------
# 사이드바 - 사용자 설정
# ----------------------------
st.sidebar.header("⚙️ 설정")

selected_names = st.sidebar.multiselect(
    "종목 선택",
    options=list(TICKERS.keys()),
    default=["🇺🇸 Apple", "🇺🇸 NVIDIA", "🇰🇷 삼성전자"]
)

period_options = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
    "2년": "2y",
    "5년": "5y",
}
period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=3)
period = period_options[period_label]

interval_options = {
    "일봉": "1d",
    "주봉": "1wk",
    "월봉": "1mo",
}
interval_label = st.sidebar.selectbox("봉 간격", list(interval_options.keys()), index=0)
interval = interval_options[interval_label]

show_volume = st.sidebar.checkbox("거래량 표시", value=True)
show_ma = st.sidebar.checkbox("이동평균선 표시 (20/60일)", value=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 캐시 초기화 후 새로고침"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("데이터 출처: Yahoo Finance")

if not selected_names:
    st.warning("사이드바에서 종목을 최소 1개 이상 선택해주세요.")
    st.stop()

# ----------------------------
# 데이터 불러오기 (캐시 30분 + 재시도 로직 + 에러 방지)
# ----------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def load_data(ticker, period, interval, _retries=3):
    for attempt in range(_retries):
        try:
            t = yf.Ticker(ticker, session=SESSION)
            df = t.history(period=period, interval=interval)
            if not df.empty:
                return df
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))  # 점점 대기시간을 늘려가며 재시도
    return pd.DataFrame()  # 끝내 실패하면 빈 DataFrame 반환

# ----------------------------
# 상단 요약 카드
# ----------------------------
st.subheader("📊 실시간 요약")
cols = st.columns(len(selected_names))

for i, name in enumerate(selected_names):
    ticker = TICKERS[name]
    df = load_data(ticker, "5d", "1d")
    if df.empty or len(df) < 2:
        cols[i].metric(name, "일시적 오류")
        continue
    last_price = df["Close"].iloc[-1]
    prev_price = df["Close"].iloc[-2]
    change = last_price - prev_price
    pct = (change / prev_price) * 100
    cols[i].metric(
        label=name,
        value=f"{last_price:,.2f}",
        delta=f"{change:,.2f} ({pct:.2f}%)"
    )

st.markdown("---")

# ----------------------------
# 개별 종목 차트
# ----------------------------
st.subheader("📈 종목별 차트")

any_success = False

for name in selected_names:
    ticker = TICKERS[name]
    df = load_data(ticker, period, interval)

    if df.empty:
        st.warning(f"⚠️ {name} 데이터를 지금은 불러올 수 없습니다 (Yahoo Finance 요청 제한). 잠시 후 '캐시 초기화 후 새로고침'을 눌러보세요.")
        continue

    any_success = True

    with st.expander(f"{name} ({ticker})", expanded=True):
        rows = 2 if show_volume else 1
        row_heights = [0.7, 0.3] if show_volume else [1.0]

        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=row_heights
        )

        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="가격",
                increasing_line_color="red",
                decreasing_line_color="blue"
            ),
            row=1, col=1
        )

        if show_ma:
            df["MA20"] = df["Close"].rolling(window=20).mean()
            df["MA60"] = df["Close"].rolling(window=60).mean()

            fig.add_trace(
                go.Scatter(x=df.index, y=df["MA20"], name="20일 이평선",
                           line=dict(color="orange", width=1.2)),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=df.index, y=df["MA60"], name="60일 이평선",
                           line=dict(color="purple", width=1.2)),
                row=1, col=1
            )

        if show_volume:
            colors = ["red" if row["Close"] >= row["Open"] else "blue"
                      for _, row in df.iterrows()]
            fig.add_trace(
                go.Bar(x=df.index, y=df["Volume"], name="거래량",
                       marker_color=colors),
                row=2, col=1
            )

        fig.update_layout(
            height=550,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=30, b=10),
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ----------------------------
# 비교 차트
# ----------------------------
if any_success:
    st.subheader("🔀 종목 간 수익률 비교 (기준일 대비 %)")

    compare_fig = go.Figure()

    for name in selected_names:
        ticker = TICKERS[name]
        df = load_data(ticker, period, interval)
        if df.empty:
            continue
        normalized = (df["Close"] / df["Close"].iloc[0] - 1) * 100
        compare_fig.add_trace(
            go.Scatter(x=df.index, y=normalized, mode="lines", name=name)
        )

    compare_fig.update_layout(
        height=500,
        yaxis_title="수익률 (%)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=30, b=10),
    )

    st.plotly_chart(compare_fig, use_container_width=True)

st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
