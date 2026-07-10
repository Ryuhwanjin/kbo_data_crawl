import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns

# Savant 구종 약어 및 브랜드 컬러 맵
SAVANT_PITCH_MAP = {
    "직구": {"abbr": "FF", "color": "#D22630"},       # 포심 패스트볼 (레드)
    "포심": {"abbr": "FF", "color": "#D22630"},
    "슬라이더": {"abbr": "SL", "color": "#20558A"},     # 슬라이더 (네이비)
    "체인지업": {"abbr": "CH", "color": "#00843D"},     # 체인지업 (그린)
    "커브": {"abbr": "CU", "color": "#B9975B"},       # 커브 (골드)
    "싱커": {"abbr": "SI", "color": "#E87722"},       # 싱커/투심 (오렌지)
    "투심": {"abbr": "SI", "color": "#E87722"},
    "포크": {"abbr": "FS", "color": "#00A3A6"},       # 스플리터/포크 (시안/민트)
    "반포크": {"abbr": "FS", "color": "#00A3A6"},
    "스플리터": {"abbr": "FS", "color": "#00A3A6"},
    "커터": {"abbr": "FC", "color": "#8A1538"},       # 커터 (버건디)
    "컷패스트볼": {"abbr": "FC", "color": "#8A1538"}
}

DEFAULT_PITCH_STYLE = {"abbr": "OT", "color": "#777777"}  # 기타 (그레이)

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

def draw_savant_pitch_chart(csv_path, pitcher_name, out_dir):
    """지정한 투수의 투구 분포를 Statcast Pitch Arsenal 스타일로 시각화합니다."""
    if not os.path.exists(csv_path):
        print(f"❌ 데이터셋 파일이 존재하지 않습니다: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    
    # 1. 대상 투수 데이터 필터링
    p_df = df[(df["pitcher_name"] == pitcher_name) & (df["plate_x"].notnull()) & (df["plate_z"].notnull())].copy()
    
    if p_df.empty:
        print(f"⚠️ {pitcher_name} 투수의 투구 데이터가 없습니다.")
        available_pitchers = df["pitcher_name"].dropna().unique()
        print(f"ℹ️ 시각화 가능한 투수 목록 (상위 10명): {', '.join(available_pitchers[:10])}")
        return
        
    print(f"🎯 {pitcher_name} 투수의 투구 {len(p_df)}구를 스탯캐스트 아스날 스타일로 분석합니다.")
    
    # 2. 스트라이크 존 박스 상하한선 평균 계산
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    # 3. 캔버스 및 한글 설정 (Seaborn 화이트 테마 설정)
    sns.set_theme(style="whitegrid", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8, 10))
    set_korean_font()
    
    # 배경 무광 백색 및 외곽 그리드선 제거 (Savant Pitch Arsenal 감성)
    ax.set_facecolor("#FFFFFF")
    ax.grid(False)
    
    # 4. 스트라이크 존 박스 채우기 (반투명 밝은 회색 음영)
    plate_width_limit = 0.7083  # 17인치 홈플레이트 가로 폭의 절반 (ft)
    sz_width = plate_width_limit * 2
    sz_height = sz_top - sz_bottom
    
    rect_sz = patches.Rectangle(
        (-plate_width_limit, sz_bottom), sz_width, sz_height,
        linewidth=2.5, edgecolor="#222222", facecolor="#F5F5F5", alpha=0.5, zorder=2
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
    home_plate = patches.Polygon(hp_pts, closed=True, facecolor="#E5E5E5", edgecolor="#555555", linewidth=1.5, zorder=1)
    ax.add_patch(home_plate)
    
    # 6. 투구 밀집 등고선 (KDE Contour Heatmap) 렌더링
    # Statcast 스타일의 부드럽고 촘촘한 밀도 대비 표현
    if len(p_df) >= 5:
        sns.kdeplot(
            x=p_df["plate_x"], y=p_df["plate_z"],
            fill=True, alpha=0.35, levels=8, cmap="Reds", zorder=1, ax=ax
        )
    
    # 7. 미니멀 원형 마커 렌더링 (글자 없이 작고 조밀하게 플롯)
    # 범례 구성을 위해 구종별로 나누어 scatter 실행
    unique_pitches = p_df["pitch_type"].dropna().unique()
    
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        style = SAVANT_PITCH_MAP.get(pitch_type, DEFAULT_PITCH_STYLE)
        
        ax.scatter(
            sub_df["plate_x"], sub_df["plate_z"],
            color=style["color"], s=60, edgecolors="#FFFFFF", linewidths=0.8, alpha=0.95, zorder=3,
            label=f"{pitch_type}"
        )
            
    # 8. 축 범위 및 레이아웃 설정 (사반트 가로세로비 매치)
    ax.set_xlim(-1.8, 1.8)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect('equal', adjustable='box')
    
    # 축 눈금 좌표 및 라벨 제거 (초미니멀 Pitch Arsenal 스타일)
    ax.set_xticks([])
    ax.set_yticks([])
    
    # 라벨 및 외곽 테두리선(Spines) 정리
    ax.set_title(f"{pitcher_name} - Statcast Pitch Arsenal\n(Catcher's View)", fontsize=16, fontweight="bold", pad=20, color="#222222")
    
    # 테두리 축 정리 (사반트는 축 외곽 경계선을 거의 없앰)
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_color("#DDDDDD")
        ax.spines[spine].set_linewidth(0.8)
        
    # 범례 배치 (우측 상단에 고급스럽게 배치)
    ax.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="#E0E0E0", shadow=True, fontsize=10)
    
    # 9. 이미지 저장
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pitcher_name}_pitch_chart.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"✅ Statcast Pitch Arsenal 스타일 피칭 분포 시각화 완료!")
    print(f"   -> {os.path.abspath(out_path)}")

def main():
    parser = argparse.ArgumentParser(description="KBO PTS 투수 피칭 존 Statcast 스타일 시각화 도구")
    parser.add_argument("--pitcher", type=str, default="주현상", help="시각화할 투수 이름 (기본값: 주현상)")
    args = parser.parse_args()
    
    csv_path = "./kbo_data/kbo_pitch_dataset.csv"
    out_dir = "./kbo_data"
    
    draw_savant_pitch_chart(csv_path, args.pitcher, out_dir)

if __name__ == "__main__":
    main()
