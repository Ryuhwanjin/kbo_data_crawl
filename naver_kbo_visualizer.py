import os
import json
import argparse
import random
import numpy as np
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

def draw_baseball_field(ax):
    """2D 야구장 필드 그래픽(내야 다이아몬드, 파울라인, 외야 펜스)을 드로잉합니다."""
    # 외곽 무광 백색 테마 설정
    ax.set_facecolor("#FFFFFF")
    ax.grid(False)
    
    # 1. 파울 라인 (홈에서 내외야 끝까지 뻗어나가는 선)
    # 홈플레이트 (0, 0) 기준 좌측 파울라인 (-250, 250), 우측 파울라인 (250, 250)
    ax.plot([0, -250], [0, 250], color="#555555", linewidth=1.5, zorder=1)
    ax.plot([0, 250], [0, 250], color="#555555", linewidth=1.5, zorder=1)
    
    # 2. 내야 다이아몬드 베이스 라인 (각 베이스간 거리 90피트, 투영 좌표 매핑)
    # 홈: (0,0), 1루: (63.6, 63.6), 2루: (0, 127.3), 3루: (-63.6, 63.6)
    ax.plot([0, 63.64], [0, 63.64], color="#BBBBBB", linewidth=1.2, linestyle="-", zorder=1)
    ax.plot([63.64, 0], [63.64, 127.28], color="#BBBBBB", linewidth=1.2, linestyle="-", zorder=1)
    ax.plot([0, -63.64], [127.28, 63.64], color="#BBBBBB", linewidth=1.2, linestyle="-", zorder=1)
    ax.plot([-63.64, 0], [63.64, 0], color="#BBBBBB", linewidth=1.2, linestyle="-", zorder=1)
    
    # 투수 마운드 서클 (반경 9피트)
    mount_circle = patches.Circle((0, 60.5), 9, facecolor="#F5EFE6", edgecolor="#DDDDDD", linewidth=1, zorder=1)
    ax.add_patch(mount_circle)
    
    # 3. 외야 펜스 라인 (반경 325피트 ~ 중앙 400피트 매치 아크 드로잉)
    # theta 범위: 좌측 파울라인 135도 ~ 우측 파울라인 45도 (포수 시점 2D 매핑상 45도 ~ 135도 범위)
    theta = np.linspace(np.pi / 4, 3 * np.pi / 4, 100)
    # 중앙 펜스를 살짝 더 멀리 그리기 위해 각도별 반경 보간 연산
    r = 310 + 40 * np.sin(2 * (theta - np.pi/4)) # 중앙 400피트, 좌우 310피트 보간 아크
    x_fence = r * np.cos(theta)
    y_fence = r * np.sin(theta)
    ax.plot(x_fence, y_fence, color="#333333", linewidth=2.0, zorder=2)
    
    # 내야 흙 영역 반원 시각화
    infield_dirt = patches.Arc((0, 60.5), 190, 190, angle=0, theta1=45, theta2=135, color="#F5EFE6", linestyle="--", linewidth=1.2, zorder=1)
    ax.add_patch(infield_dirt)
    
    # 4. 베이스 사각형 기입
    # 1루, 2루, 3루
    ax.scatter([63.64], [63.64], marker="s", color="#FFFFFF", s=50, edgecolors="gray", zorder=2)
    ax.scatter([0], [127.28], marker="s", color="#FFFFFF", s=50, edgecolors="gray", zorder=2)
    ax.scatter([-63.64], [63.64], marker="s", color="#FFFFFF", s=50, edgecolors="gray", zorder=2)
    # 홈플레이트 (0, 0)
    ax.scatter([0], [0], marker="D", color="#FFFFFF", s=60, edgecolors="black", zorder=2)

def parse_bat_comment_to_coordinates(text):
    """문자중계 텍스트를 파싱하여 야구장 2D 평면상의 타구 도달 위치(x, y) 및 결과를 반환합니다."""
    text = str(text)
    
    # 1. 안타 유형 세분화 (아웃 및 기타 기록 제외)
    is_hr = "홈런" in text
    is_triple = "3루타" in text
    is_double = "2루타" in text
    is_single = any(x in text for x in ["안타", "적시타", "결승타", "1루타"]) and not (is_hr or is_triple or is_double)
    
    if not (is_hr or is_triple or is_double or is_single):
        return None, None, None
        
    if is_hr:
        result_type = "HR"
    elif is_triple:
        result_type = "TRIPLE"
    elif is_double:
        result_type = "DOUBLE"
    else:
        result_type = "SINGLE"
    
    # 2. 수비수 및 타구 방향 키워드 기반 표준 각도 설정
    angle = 0.0
    
    # 방향 설정 (각도만 유도)
    if any(x in text for x in ["좌익수", "좌중간", "왼쪽"]):
        angle = random.uniform(-40, -15)
    elif any(x in text for x in ["우익수", "우중간", "오른쪽"]):
        angle = random.uniform(15, 40)
    elif any(x in text for x in ["중견수", "가운데", "센터"]):
        angle = random.uniform(-15, 15)
    elif any(x in text for x in ["유격수", "3루수", "3루"]):
        angle = random.uniform(-35, -15)
    elif any(x in text for x in ["2루수", "1루수", "1루"]):
        angle = random.uniform(15, 35)
    elif "투수" in text:
        angle = random.uniform(-10, 10)
    elif "포수" in text:
        angle = random.uniform(-40, 40)
    else:
        angle = random.uniform(-40, 40)
        
    # 구질별 사실적인 비행 거리 가중치 조정
    if result_type == "SINGLE":
        distance = random.uniform(140, 200)
    elif result_type == "DOUBLE":
        distance = random.uniform(220, 270)
    elif result_type == "TRIPLE":
        distance = random.uniform(240, 290)
    elif result_type == "HR":
        distance = random.uniform(330, 375)
        
    # 3. 각도와 거리로부터 2D x, y 좌표 산출
    rad = np.radians(angle)
    x = distance * np.sin(rad)
    y = distance * np.cos(rad)
    
    return x, y, result_type

def draw_savant_pitch_chart(csv_path, pitcher_name, year, out_dir):
    """지정한 투수의 투구 분포를 'Contour Only' 스타일로 시각화합니다. (기존 구현 유지)"""
    df = pd.read_csv(csv_path)
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    
    p_df = df[(df["pitcher_name"] == pitcher_name) & (df["plate_x"].notnull()) & (df["plate_z"].notnull())].copy()
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
    
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    sns.set_theme(style="whitegrid", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    fig, axes = plt.subplots(1, len(p_df["pitch_type"].dropna().unique()), figsize=(4.2 * len(p_df["pitch_type"].dropna().unique()), 5.2), squeeze=False)
    set_korean_font()
    
    plate_width_limit = 0.7083
    sz_width = plate_width_limit * 2
    sz_height = sz_top - sz_bottom
    hp_pts = [[-plate_width_limit, 0], [plate_width_limit, 0], [plate_width_limit, -0.15], [0, -0.3], [-plate_width_limit, -0.15]]
    
    unique_pitches = p_df["pitch_type"].dropna().unique()
    pitch_report_list = []
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        style = SAVANT_PITCH_MAP.get(pitch_type, DEFAULT_PITCH_STYLE)
        count = len(sub_df)
        usage_pct = (count / total_pitches) * 100
        if count >= 4:
            pitch_report_list.append({
                "type": pitch_type, "count": count, "pct": usage_pct,
                "color": style["color"], "cmap": style["cmap"], "df": sub_df
            })
            
    pitch_report_list.sort(key=lambda x: x["count"], reverse=True)
    
    for i, item in enumerate(pitch_report_list):
        ax = axes[0, i]
        ax.set_facecolor("#FFFFFF")
        ax.grid(False)
        rect_sz = patches.Rectangle((-plate_width_limit, sz_bottom), sz_width, sz_height, linewidth=2.2, edgecolor="#222222", facecolor="#F8F8F8", alpha=0.6, zorder=2)
        ax.add_patch(rect_sz)
        home_plate = patches.Polygon(hp_pts, closed=True, facecolor="#E0E0E0", edgecolor="#666666", linewidth=1.2, zorder=1)
        ax.add_patch(home_plate)
        sns.kdeplot(x=item["df"]["plate_x"], y=item["df"]["plate_z"], fill=True, alpha=0.35, levels=6, cmap=item["cmap"], thresh=0.15, zorder=3, ax=ax)
        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-0.5, 4.4)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_color("#DDDDDD")
            ax.spines[spine].set_linewidth(0.8)
        ax.set_title(f"{item['type']}\n({item['count']}구, {item['pct']:.1f}%)", fontsize=11, fontweight="bold", color="#333333", pad=10)
        
    fig.suptitle(f"{pitcher_name} ({year_label}) - Pitch Heatmap", fontsize=15, fontweight="bold", y=0.98, color="#111111")
    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_{year}" if year is not None else ""
    out_path = os.path.join(out_dir, f"{pitcher_name}{suffix}_pitch_chart.png")
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"✅ 구종별 다중 패널 시각화 완료! 차트 저장 경로:\n   -> {os.path.abspath(out_path)}")

def generate_pitch_chart_fig(df, pitcher_name, year):
    """지정한 투수의 투구 분포를 메모리 기반 Matplotlib Figure 객체로 생성해 반환합니다. (Streamlit 최적화용)"""
    p_df = df[(df["pitcher_name"] == pitcher_name) & (df["plate_x"].notnull()) & (df["plate_z"].notnull())].copy()
    
    if year is not None:
        p_df = p_df[p_df["year"] == year]
        year_label = f"{year}년"
    else:
        year_label = "전체 시즌"
        
    if p_df.empty:
        return None
        
    total_pitches = len(p_df)
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    sns.set_theme(style="whitegrid", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    
    unique_pitches = p_df["pitch_type"].dropna().unique()
    pitch_report_list = []
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        style = SAVANT_PITCH_MAP.get(pitch_type, DEFAULT_PITCH_STYLE)
        count = len(sub_df)
        usage_pct = (count / total_pitches) * 100
        if count >= 4:
            pitch_report_list.append({
                "type": pitch_type, "count": count, "pct": usage_pct,
                "color": style["color"], "cmap": style["cmap"], "df": sub_df
            })
            
    if not pitch_report_list:
        return None
        
    pitch_report_list.sort(key=lambda x: x["count"], reverse=True)
    
    fig, axes = plt.subplots(1, len(pitch_report_list), figsize=(4.2 * len(pitch_report_list), 5.2), squeeze=False)
    
    plate_width_limit = 0.7083
    sz_width = plate_width_limit * 2
    sz_height = sz_top - sz_bottom
    hp_pts = [[-plate_width_limit, 0], [plate_width_limit, 0], [plate_width_limit, -0.15], [0, -0.3], [-plate_width_limit, -0.15]]
    
    for i, item in enumerate(pitch_report_list):
        ax = axes[0, i]
        ax.set_facecolor("#FFFFFF")
        ax.grid(False)
        rect_sz = patches.Rectangle((-plate_width_limit, sz_bottom), sz_width, sz_height, linewidth=2.2, edgecolor="#222222", facecolor="#F8F8F8", alpha=0.6, zorder=2)
        ax.add_patch(rect_sz)
        home_plate = patches.Polygon(hp_pts, closed=True, facecolor="#E0E0E0", edgecolor="#666666", linewidth=1.2, zorder=1)
        ax.add_patch(home_plate)
        sns.kdeplot(x=item["df"]["plate_x"], y=item["df"]["plate_z"], fill=True, alpha=0.35, levels=6, cmap=item["cmap"], thresh=0.15, zorder=3, ax=ax)
        
        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-0.5, 4.4)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_color("#DDDDDD")
            ax.spines[spine].set_linewidth(0.8)
        ax.set_title(f"{item['type']}\n({item['count']}구, {item['pct']:.1f}%)", fontsize=11, fontweight="bold", color="#333333", pad=10)
        
    fig.suptitle(f"{pitcher_name} ({year_label}) - Pitch Heatmap", fontsize=15, fontweight="bold", y=0.98, color="#111111")
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    return fig

def draw_batter_spray_chart(csv_path, batter_name, year, out_dir):
    """지정한 타자의 문자중계 데이터를 분석하여 2D 야구장 스프레이 차트를 시각화합니다."""
    # 1. 원본 JSON 파일들을 돌며 지정한 타자의 타석 최종 텍스트 수집
    import glob
    root_dir = "./kbo_data"
    search_path = os.path.join(root_dir, "**", "kbo_relay_*.json")
    json_files = glob.glob(search_path, recursive=True)
    
    if year is not None:
        year_label = f"{year}년"
    else:
        year_label = "전체 시즌"
        
    spray_records = []
    seen_plays = set() # 동일 플레이의 중복 집계 방지 (날짜 + 타석번호)
    
    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except:
            continue
            
        result_data = raw_data.get("result", {})
        text_relay_data = result_data.get("textRelayData", {})
        if not text_relay_data:
            continue
            
        game_id = text_relay_data.get("gameId", "Unknown")
        game_year = None
        try:
            game_year = int(game_id[:4])
        except:
            pass
            
        # 연도 필터링
        if year is not None and game_year != year:
            continue
            
        # 선수 이름 매핑
        player_map = {}
        for side in ["homeLineup", "awayLineup"]:
            lineup = text_relay_data.get(side, {})
            for player in lineup.get("batter", []):
                if player.get("pcode"):
                    player_map[str(player["pcode"])] = player.get("name")
                    
        relays = text_relay_data.get("textRelays", [])
        for tr in relays:
            # textOptions 중 첫 번째나 임의의 원소에서 batter pcode를 획득합니다.
            batter_code = None
            for opt in tr.get("textOptions", []):
                state = opt.get("currentGameState", {})
                if state.get("batter"):
                    batter_code = str(state["batter"])
                    break
            
            if not batter_code:
                continue
                
            batter_pname = player_map.get(batter_code, batter_code)
            
            if batter_pname == batter_name:
                play_key = f"{game_id}_{tr.get('no', 0)}"
                if play_key in seen_plays:
                    continue
                seen_plays.add(play_key)
                
                # 텍스트 병합 (타석 타이틀 + 중계 설명글)
                merged_text = tr.get("title", "") + " "
                for opt in tr.get("textOptions", []):
                    merged_text += opt.get("text", "") + " "
                    
                # 좌표 및 타입 추출
                x, y, rtype = parse_bat_comment_to_coordinates(merged_text)
                if x is not None:
                    spray_records.append({
                        "x": x,
                        "y": y,
                        "type": rtype,
                        "text": merged_text
                    })
            
    total_batted_balls = len(spray_records)
    print("=" * 60)
    print(f"📊 [{batter_name}] 타자의 {year_label} 타구 분포 분석 (Spray Chart)")
    print(f"   집계된 총 인플레이 타구: {total_batted_balls}개")
    print("=" * 60)
    
    if total_batted_balls == 0:
        print(f"❌ {batter_name} 타자의 인플레이 타구(안타/홈런/아웃 텍스트)가 존재하지 않습니다.")
        return
        
    df_spray = pd.DataFrame(spray_records)
    
    # 3. 캔버스 및 한글 폰트 설정
    sns.set_theme(style="white", rc={"font.family": "AppleGothic", "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(9, 9))
    set_korean_font()
    
    # 2D 야구 필드 배경 그리기
    draw_baseball_field(ax)
    
    # 4. 안타 유형별 마커 및 컬러 플로팅
    # 단타 (SINGLE) - 초록색 원형 마커
    singles = df_spray[df_spray["type"] == "SINGLE"]
    if not singles.empty:
        ax.scatter(
            singles["x"], singles["y"],
            color="#2ECC71", marker="o", s=80, edgecolors="#FFFFFF", linewidths=0.8, alpha=0.9,
            label=f"단타 ({len(singles)}개)"
        )
        
    # 2루타 (DOUBLE) - 파란색 사각형 마커
    doubles = df_spray[df_spray["type"] == "DOUBLE"]
    if not doubles.empty:
        ax.scatter(
            doubles["x"], doubles["y"],
            color="#3498DB", marker="s", s=80, edgecolors="#FFFFFF", linewidths=0.8, alpha=0.9,
            label=f"2루타 ({len(doubles)}개)"
        )
        
    # 3루타 (TRIPLE) - 보라색 다이아몬드 마커
    triples = df_spray[df_spray["type"] == "TRIPLE"]
    if not triples.empty:
        ax.scatter(
            triples["x"], triples["y"],
            color="#9B59B6", marker="D", s=90, edgecolors="#FFFFFF", linewidths=0.8, alpha=0.95,
            label=f"3루타 ({len(triples)}개)"
        )
        
    # 홈런 (HR) - 황금색 별 마커
    hrs = df_spray[df_spray["type"] == "HR"]
    if not hrs.empty:
        ax.scatter(
            hrs["x"], hrs["y"],
            color="#F1C40F", marker="*", s=160, edgecolors="#D68910", linewidths=0.8, alpha=0.95,
            label=f"홈런 ({len(hrs)}개)"
        )
        
    # 5. 축 한계 및 레이아웃 정리 (야구장 한 뷰로 보이기 조율)
    ax.set_xlim(-260, 260)
    ax.set_ylim(-30, 420)
    ax.set_aspect('equal', adjustable='box')
    
    # 축 좌표 눈금 숨기기
    ax.set_xticks([])
    ax.set_yticks([])
    
    # 테두리 축 지우기
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)
        
    # 타이틀 기입
    ax.set_title(f"{batter_name} ({year_label}) - Spray Chart", fontsize=16, fontweight="bold", pad=15, color="#222222")
    
    # 범례 배치
    ax.legend(loc="upper right", frameon=True, facecolor="#FFFFFF", edgecolor="#E0E0E0", shadow=True, fontsize=10)
    
    # 6. 이미지 저장
    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_{year}" if year is not None else ""
    out_path = os.path.join(out_dir, f"{batter_name}{suffix}_spray_chart.png")
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"✅ 타구 스프레이 시각화 완료! 차트 저장 경로:")
    print(f"   -> {os.path.abspath(out_path)}")

def main():
    parser = argparse.ArgumentParser(description="KBO PTS 투수 피칭 존 및 타자 스프레이 차트 시각화 도구")
    parser.add_argument("--pitcher", type=str, default=None, help="시각화할 투수 이름")
    parser.add_argument("--batter", type=str, default=None, help="시각화할 타자 이름")
    parser.add_argument("--year", type=int, default=None, help="시각화할 연도 (기본값: None, 전체 연도)")
    args = parser.parse_args()
    
    csv_path = "./kbo_data/kbo_pitch_dataset.csv"
    out_dir = "./kbo_data"
    
    # 투수명과 타자명 입력 여부에 따라 실행 모드 자동 분기
    if args.pitcher:
        draw_savant_pitch_chart(csv_path, args.pitcher, args.year, out_dir)
    elif args.batter:
        draw_batter_spray_chart(csv_path, args.batter, args.year, out_dir)
    else:
        # 둘 다 지정하지 않았을 때 기본값으로 주현상 투수 차트 실행
        print("ℹ️ 투수(--pitcher) 또는 타자(--batter) 이름을 지정해 주세요. 기본값으로 주현상 투수 차트를 렌더링합니다.")
        draw_savant_pitch_chart(csv_path, "주현상", args.year, out_dir)

if __name__ == "__main__":
    main()
