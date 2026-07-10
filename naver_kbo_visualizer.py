import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns

# Savant 구종 약어, 브랜드 컬러 및 등고선 cmap 맵
SAVANT_PITCH_MAP = {
    "직구": {"abbr": "FF", "color": "#D22630", "cmap": "Reds"},       # 포심 패스트볼 (레드)
    "포심": {"abbr": "FF", "color": "#D22630", "cmap": "Reds"},
    "슬라이더": {"abbr": "SL", "color": "#20558A", "cmap": "Blues"},     # 슬라이더 (블루)
    "체인지업": {"abbr": "CH", "color": "#00843D", "cmap": "Greens"},    # 체인지업 (그린)
    "커브": {"abbr": "CU", "color": "#B9975B", "cmap": "Oranges"},     # 커브 (오렌지/브라운)
    "싱커": {"abbr": "SI", "color": "#E87722", "cmap": "YlOrBr"},      # 싱커/투심
    "투심": {"abbr": "SI", "color": "#E87722", "cmap": "YlOrBr"},
    "포크": {"abbr": "FS", "color": "#00A3A6", "cmap": "Purples"},     # 스플리터/포크 (퍼플)
    "반포크": {"abbr": "FS", "color": "#00A3A6", "cmap": "Purples"},
    "스플리터": {"abbr": "FS", "color": "#00A3A6", "cmap": "Purples"},
    "커터": {"abbr": "FC", "color": "#8A1538", "cmap": "RdPu"},        # 커터 (핑크/버건디)
    "컷패스트볼": {"abbr": "FC", "color": "#8A1538", "cmap": "RdPu"}
}

DEFAULT_PITCH_STYLE = {"abbr": "OT", "color": "#777777", "cmap": "Greys"}  # 기타 (그레이)

def set_korean_font():
    """macOS 환경에 맞추어 한글 폰트를 강제로 설정합니다."""
    from matplotlib import font_manager, rc
    font_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    if os.path.exists(font_path):
        font_name = font_manager.FontProperties(fname=font_path).get_name()
        rc('font', family=font_name)
    else:
        plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams['axes.unicode_minus'] = False

def draw_savant_pitch_chart(csv_path, pitcher_name, year, out_dir):
    """지정한 투수의 투구 분포를 구종별 개별 패널(Subplots)로 나누어 'Pitch Heatmap' 스타일로 시각화합니다."""
    if not os.path.exists(csv_path):
        print(f"❌ 데이터셋 파일이 존재하지 않습니다: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    
    # 날짜로부터 연도 파싱
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    
    # 1. 대상 투수 데이터 필터링
    p_df = df[(df["pitcher_name"] == pitcher_name) & (df["plate_x"].notnull()) & (df["plate_z"].notnull())].copy()
    
    # 연도 필터링
    if year is not None:
        p_df = p_df[p_df["year"] == year]
        year_label = f"{year}년"
    else:
        year_label = "전체 시즌"
        
    if p_df.empty:
        print(f"⚠️ {pitcher_name} 투수의 {year_label} 투구 데이터가 없습니다.")
        return
        
    total_pitches = len(p_df)
    print("=" * 60)
    print(f"📊 [{pitcher_name}] 투수의 {year_label} 구종 아스날 분석")
    print(f"   총 투구 수: {total_pitches}구")
    print("=" * 60)
    
    # 2. 스트라이크 존 박스 높이 산출 (투수 고유 값)
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    # 3. 구종별 데이터 및 비율 연산
    unique_pitches = p_df["pitch_type"].dropna().unique()
    pitch_report_list = []
    
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        style = SAVANT_PITCH_MAP.get(pitch_type, DEFAULT_PITCH_STYLE)
        
        count = len(sub_df)
        usage_pct = (count / total_pitches) * 100
        
        # 등고선 렌더링이 가능한 유효 구종 (최소 4구 이상 투구)만 시각화 대상으로 선택
        if count >= 4:
            pitch_report_list.append({
                "type": pitch_type,
                "count": count,
                "pct": usage_pct,
                "color": style["color"],
                "cmap": style["cmap"],
                "df": sub_df
            })
            
    # 투구 구사율 높은 순으로 정렬
    pitch_report_list.sort(key=lambda x: x["count"], reverse=True)
    
    # 정렬된 순으로 콘솔 출력
    for item in pitch_report_list:
        print(f"  - {item['type']}: {item['count']}구 ({item['pct']:.1f}%)")
    print("=" * 60)
    
    M = len(pitch_report_list)
    if M == 0:
        print("❌ 등고선을 그릴 수 있는 유효 구종(4구 이상 투구)이 없습니다.")
        return
        
    # 4. 캔버스 및 한글 설정 (Seaborn 화이트 테마 설정)
    sns.set_theme(style="whitegrid", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    
    # 구종 개수 M만큼 가로형 서브플롯 동적 배치
    fig, axes = plt.subplots(1, M, figsize=(4.2 * M, 5.2), squeeze=False)
    set_korean_font()
    
    # 5. 각 구종별 개별 패널 렌더링
    plate_width_limit = 0.7083  # 17인치 홈플레이트 가로 폭의 절반 (ft)
    sz_width = plate_width_limit * 2
    sz_height = sz_top - sz_bottom
    
    hp_pts = [
        [-plate_width_limit, 0],
        [plate_width_limit, 0],
        [plate_width_limit, -0.15],
        [0, -0.3],
        [-plate_width_limit, -0.15]
    ]
    
    for i, item in enumerate(pitch_report_list):
        ax = axes[0, i]
        
        # 배경 세팅
        ax.set_facecolor("#FFFFFF")
        ax.grid(False)
        
        # 스트라이크 존 박스 채우기
        rect_sz = patches.Rectangle(
            (-plate_width_limit, sz_bottom), sz_width, sz_height,
            linewidth=2.2, edgecolor="#222222", facecolor="#F8F8F8", alpha=0.6, zorder=2
        )
        ax.add_patch(rect_sz)
        
        # 홈플레이트 드로잉
        home_plate = patches.Polygon(hp_pts, closed=True, facecolor="#E0E0E0", edgecolor="#666666", linewidth=1.2, zorder=1)
        ax.add_patch(home_plate)
        
        # 구종 단독 등고선(KDE) 렌더링
        sns.kdeplot(
            x=item["df"]["plate_x"], y=item["df"]["plate_z"],
            fill=True, alpha=0.35, levels=6, cmap=item["cmap"], thresh=0.15, zorder=3, ax=ax
        )
        
        # 축 및 눈금 감추기
        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-0.5, 4.4)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xticks([])
        ax.set_yticks([])
        
        # 외곽 스파인 라인 정리
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_color("#DDDDDD")
            ax.spines[spine].set_linewidth(0.8)
            
        # 개별 패널 헤더 타이틀 작성 (구종명 & 구사 지표)
        ax.set_title(f"{item['type']}\n({item['count']}구, {item['pct']:.1f}%)", fontsize=11, fontweight="bold", color="#333333", pad=10)
        
    # 6. 전역 차트 타이틀 (사용자 요청: 'Pitch Heatmap')
    fig.suptitle(f"{pitcher_name} ({year_label}) - Pitch Heatmap", fontsize=15, fontweight="bold", y=0.98, color="#111111")
    
    # 7. 이미지 저장 (연도 세분화 파일명 유지)
    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_{year}" if year is not None else ""
    out_path = os.path.join(out_dir, f"{pitcher_name}{suffix}_pitch_chart.png")
    
    plt.tight_layout(rect=[0, 0, 1, 0.93]) # suptitle 공간을 확보하기 위해 상단 레이아웃 빈 마진 적용
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"✅ 구종별 다중 패널 시각화 완료! 차트 저장 경로:")
    print(f"   -> {os.path.abspath(out_path)}")

def main():
    parser = argparse.ArgumentParser(description="KBO PTS 투수 피칭 존 다중 패널 시각화 도구")
    parser.add_argument("--pitcher", type=str, default="주현상", help="시각화할 투수 이름 (기본값: 주현상)")
    parser.add_argument("--year", type=int, default=None, help="시각화할 연도 (기본값: None, 전체 연도)")
    args = parser.parse_args()
    
    csv_path = "./kbo_data/kbo_pitch_dataset.csv"
    out_dir = "./kbo_data"
    
    draw_savant_pitch_chart(csv_path, args.pitcher, args.year, out_dir)

if __name__ == "__main__":
    main()
