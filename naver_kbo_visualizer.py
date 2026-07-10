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
    """지정한 투수의 투구 분포를 연도별/구종 구사율과 함께 'Contour Only' 스타일로 시각화합니다."""
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
        available_years = df[df["pitcher_name"] == pitcher_name]["year"].dropna().unique()
        print(f"ℹ️ {pitcher_name} 투수 수집 완료 연도 목록: {', '.join(map(str, map(int, available_years)))}")
        return
        
    total_pitches = len(p_df)
    print("=" * 60)
    print(f"📊 [{pitcher_name}] 투수의 {year_label} 구종 아스날 분석")
    print(f"   총 투구 수: {total_pitches}구")
    print("=" * 60)
    
    # 2. 스트라이크 존 박스 상하한선 평균 계산
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    # 3. 캔버스 및 한글 설정
    sns.set_theme(style="whitegrid", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8, 10))
    set_korean_font()
    
    # 배경 무광 백색 및 외곽 그리드선 제거
    ax.set_facecolor("#FFFFFF")
    ax.grid(False)
    
    # 4. 스트라이크 존 박스 채우기 (반투명 밝은 회색 음영)
    plate_width_limit = 0.7083  # 17인치 홈플레이트 가로 폭의 절반 (ft)
    sz_width = plate_width_limit * 2
    sz_height = sz_top - sz_bottom
    
    rect_sz = patches.Rectangle(
        (-plate_width_limit, sz_bottom), sz_width, sz_height,
        linewidth=2.5, edgecolor="#222222", facecolor="#F8F8F8", alpha=0.6, zorder=2
    )
    ax.add_patch(rect_sz)
    
    # 5. 홈플레이트 드로잉 (Savant 블랙 플랫 디자인)
    hp_pts = [
        [-plate_width_limit, 0],
        [plate_width_limit, 0],
        [plate_width_limit, -0.15],
        [0, -0.3],
        [-plate_width_limit, -0.15]
    ]
    home_plate = patches.Polygon(hp_pts, closed=True, facecolor="#E0E0E0", edgecolor="#666666", linewidth=1.5, zorder=1)
    ax.add_patch(home_plate)
    
    # 6. 구종별 2D 등고선(KDE Contour) 오버랩 렌더링 및 비율 연산
    unique_pitches = p_df["pitch_type"].dropna().unique()
    legend_elements = []
    
    # 비율순 정렬을 위해 임시 저장
    pitch_report_list = []
    
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        style = SAVANT_PITCH_MAP.get(pitch_type, DEFAULT_PITCH_STYLE)
        
        count = len(sub_df)
        usage_pct = (count / total_pitches) * 100
        
        pitch_report_list.append({
            "type": pitch_type,
            "count": count,
            "pct": usage_pct,
            "color": style["color"],
            "cmap": style["cmap"],
            "df": sub_df
        })
        
    # 구사율 높은 순으로 정렬하여 콘솔 출력 및 범례 생성
    pitch_report_list.sort(key=lambda x: x["count"], reverse=True)
    
    for item in pitch_report_list:
        p_type = item["type"]
        cnt = item["count"]
        pct = item["pct"]
        sub_df = item["df"]
        
        # 콘솔 리포트 출력
        print(f"  - {p_type}: {cnt}구 ({pct:.1f}%)")
        
        # KDE는 표본 데이터 수가 극도로 적으면 계산 분산 에러가 나므로 최소 4구 이상 조건 적용
        if cnt >= 4:
            sns.kdeplot(
                x=sub_df["plate_x"], y=sub_df["plate_z"],
                fill=True, alpha=0.25, levels=5, cmap=item["cmap"], thresh=0.15, zorder=3, ax=ax
            )
        
        # 범례 레이블에 구구/구사율을 포함하여 사반트 아스날 서식 완성
        label_text = f"{p_type} ({cnt}구, {pct:.1f}%)"
        legend_elements.append(patches.Patch(color=item["color"], label=label_text))
        
    print("=" * 60)
    
    # 7. 축 범위 및 레이아웃 설정
    ax.set_xlim(-1.8, 1.8)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect('equal', adjustable='box')
    
    # 축 눈금 좌표 및 라벨 제거 (초미니멀 Pitch Arsenal 스타일)
    ax.set_xticks([])
    ax.set_yticks([])
    
    # 라벨 및 외곽 테두리선(Spines) 정리
    ax.set_title(f"{pitcher_name} ({year_label}) - Pitch Arsenal Heatmap\n(Contour Only / Catcher's View)", fontsize=15, fontweight="bold", pad=20, color="#222222")
    
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_color("#DDDDDD")
        ax.spines[spine].set_linewidth(0.8)
        
    # 범례 배치 (우측 상단에 고급스럽게 배치)
    if legend_elements:
        ax.legend(handles=legend_elements, loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="#E0E0E0", shadow=True, fontsize=10)
    
    # 8. 이미지 저장 (연도별 파일명 세분화 적용)
    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_{year}" if year is not None else ""
    out_path = os.path.join(out_dir, f"{pitcher_name}{suffix}_pitch_chart.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"✅ 시각화 완료! 차트 저장 경로:")
    print(f"   -> {os.path.abspath(out_path)}")

def main():
    parser = argparse.ArgumentParser(description="KBO PTS 투수 피칭 존 연도/구사율 연계 시각화 도구")
    parser.add_argument("--pitcher", type=str, default="주현상", help="시각화할 투수 이름 (기본값: 주현상)")
    parser.add_argument("--year", type=int, default=None, help="시각화할 연도 (기본값: None, 전체 연도)")
    args = parser.parse_args()
    
    csv_path = "./kbo_data/kbo_pitch_dataset.csv"
    out_dir = "./kbo_data"
    
    draw_savant_pitch_chart(csv_path, args.pitcher, args.year, out_dir)

if __name__ == "__main__":
    main()
