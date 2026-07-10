import os
import pandas as pd
import streamlit as st
from naver_kbo_visualizer import draw_savant_pitch_chart

# 1. 페이지 레이아웃 및 테마 설정
st.set_page_config(
    page_title="KBO PTS 투수 피칭 분석 대시보드",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Rich Aesthetics - 프리미엄 스포츠 디자인 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    /* 전역 폰트 지정 */
    html, body, [class*="css"] {
        font-family: 'Outfit', 'AppleGothic', sans-serif;
    }
    
    /* 타이틀 영역 그라데이션 */
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1f4068 0%, #162447 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
        padding-top: 0.5rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #555555;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* 프리미엄 스탯 카드 디자인 */
    .stat-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        border: 1px solid #EFEFEF;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    }
    .stat-val {
        font-size: 2.0rem;
        font-weight: 800;
        color: #1f4068;
        margin-bottom: 0.2rem;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #888888;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
</style>
""", unsafe_allow_html=True)

# 데이터셋 로드 헬퍼 함수 (캐싱 적용)
@st.cache_data
def load_base_datasets():
    dataset_path = "./kbo_data/kbo_pitch_dataset.csv"
    pitcher_sum_path = "./kbo_data/kbo_pitcher_summary.csv"
    
    df_raw = pd.read_csv(dataset_path) if os.path.exists(dataset_path) else pd.DataFrame()
    df_raw["year"] = pd.to_datetime(df_raw["date"], errors="coerce").dt.year
    
    df_pit_sum = pd.read_csv(pitcher_sum_path) if os.path.exists(pitcher_sum_path) else pd.DataFrame()
    
    return df_raw, df_pit_sum

df_raw, df_pit_sum = load_base_datasets()

# 3. 메인 타이틀 헤더 렌더링
st.markdown("<div class='main-title'>⚾️ KBO PTS Pitcher Analysis Dashboard</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>네이버 스포츠 PTS 3D 좌표 및 중계 로그 기반 고해상도 구종별 피칭 분석 대시보드</div>", unsafe_allow_html=True)
st.markdown("---")

if df_raw.empty:
    st.error("❌ KBO 데이터셋 파일이 존재하지 않거나 비어 있습니다. 파이프라인(`naver_kbo_pipeline.py`)을 먼저 구동해 주세요.")
    st.stop()

# 4. 사이드바 - 투수 제어 패널 구성
st.sidebar.markdown("### 🎛️ 투수 분석 제어 센터")
out_dir = "./kbo_data"

# 사용 가능한 투수 목록 (정렬)
available_pitchers = sorted(df_raw["pitcher_name"].dropna().unique())
selected_pitcher = st.sidebar.selectbox(
    "🎯 투수 선택", 
    available_pitchers, 
    index=available_pitchers.index("주현상") if "주현상" in available_pitchers else 0
)

# 선택된 투수의 가용 연도 목록 조회
pitcher_years = sorted(df_raw[df_raw["pitcher_name"] == selected_pitcher]["year"].dropna().unique())
year_options = ["전체 시즌"] + [str(int(y)) for y in pitcher_years]
selected_year_str = st.sidebar.selectbox("📅 연도 선택", year_options)

year_val = None if selected_year_str == "전체 시즌" else int(selected_year_str)

# 5. 스탯 카드 레이아웃 (투수 지표 매핑)
st.subheader(f"📊 {selected_pitcher} 투수의 {selected_year_str} 세이버메트릭스 요약")

# 요약 스탯 데이터 조회
p_stat = df_pit_sum[df_pit_sum["player_name"] == selected_pitcher]

c1, c2, c3, c4, c5 = st.columns(5)

if not p_stat.empty:
    stat_row = p_stat.iloc[0]
    era = f"{stat_row.get('ERA', 0.0):.2f}"
    whip = f"{stat_row.get('WHIP', 0.0):.2f}"
    ip = f"{stat_row.get('IP_float', 0.0):.1f}"
    h_avg = f"{stat_row.get('AVG', 0.0):.3f}"
    so = int(stat_row.get("SO", 0))
else:
    # 요약 파일에 없을 때 데이터셋에서 실시간 기본 집계
    p_df = df_raw[df_raw["pitcher_name"] == selected_pitcher]
    era = "N/A"
    whip = "N/A"
    ip = "N/A"
    h_avg = "N/A"
    so = len(p_df[p_df["pitch_result"] == "S"])
    
with c1:
    st.markdown(f"<div class='stat-card'><div class='stat-val'>{era}</div><div class='stat-label'>평균자책점 (ERA)</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='stat-card'><div class='stat-val'>{whip}</div><div class='stat-label'>출루허용률 (WHIP)</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='stat-card'><div class='stat-val'>{ip}</div><div class='stat-label'>소화 이닝 (IP)</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div class='stat-card'><div class='stat-val'>{h_avg}</div><div class='stat-label'>피안타율 (AVG)</div></div>", unsafe_allow_html=True)
with c5:
    st.markdown(f"<div class='stat-card'><div class='stat-val'>{so}</div><div class='stat-label'>탈삼진 (SO)</div></div>", unsafe_allow_html=True)
    
st.markdown("<br>", unsafe_allow_html=True)

# 6. 실시간 구종별 상세 태뷸러 데이터(Tabular Data) 생성 및 표출
st.subheader("📋 구종별 상세 투구 통계 (Tabular Data)")

# 투수별 데이터 필터링
p_df_all = df_raw[df_raw["pitcher_name"] == selected_pitcher]
if year_val is not None:
    p_df_all = p_df_all[p_df_all["year"] == year_val]

if not p_df_all.empty:
    total_pitches = len(p_df_all)
    summary_rows = []
    
    # 구종(pitch_type) 별로 그룹바이 연산
    for pitch_type, group in p_df_all.groupby("pitch_type", dropna=False):
        p_name = pitch_type if pd.notna(pitch_type) else "미분류"
        count = len(group)
        usage = (count / total_pitches) * 100
        
        # 구속 평균 및 최고값 연산
        speeds = group["speed_kmh"].dropna()
        avg_speed = speeds.mean() if not speeds.empty else None
        max_speed = speeds.max() if not speeds.empty else None
        
        # 스트라이크 비율 연산 (S: 루킹/헛스윙, F: 파울, T: 타격파울 등 스트라이크 계열 분류)
        strikes = group[group["pitch_result"].isin(["S", "F", "T", "K"])]
        strike_pct = (len(strikes) / count) * 100 if count > 0 else 0.0
        
        summary_rows.append({
            "구종": p_name,
            "투구 수 (구)": count,
            "구사율 (%)": round(usage, 1),
            "평균 구속 (km/h)": round(avg_speed, 1) if avg_speed else "-",
            "최고 구속 (km/h)": round(max_speed, 1) if max_speed else "-",
            "스트라이크 비율 (%)": round(strike_pct, 1)
        })
        
    df_pitch_summary = pd.DataFrame(summary_rows).sort_values(by="투구 수 (구)", ascending=False)
    
    # 테이블 인터랙티브 드로잉
    st.dataframe(df_pitch_summary, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ 해당 조건의 상세 투구 데이터가 없습니다.")

st.markdown("<br>", unsafe_allow_html=True)

# 7. 투수 시각화 차트 생성 및 임베딩
st.subheader("🎯 구종별 3분할 Pitch Heatmap")

# 시각화 함수 호출 (로컬에 이미지 렌더링 파일 저장)
with st.spinner("구종별 피칭 분석 맵 렌더링 중..."):
    draw_savant_pitch_chart(os.path.join(out_dir, "kbo_pitch_dataset.csv"), selected_pitcher, year_val, out_dir)
    
# 저장된 파일명 연동 로드
suffix = f"_{year_val}" if year_val is not None else ""
chart_img_path = os.path.join(out_dir, f"{selected_pitcher}{suffix}_pitch_chart.png")

if os.path.exists(chart_img_path):
    st.image(chart_img_path, width="stretch")
else:
    st.warning("⚠️ 시각화 차트를 생성하지 못했습니다. 투구 수(최소 4구 이상 조건)가 부족할 수 있습니다.")
