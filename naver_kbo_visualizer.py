import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def set_korean_font():
    """macOS 환경에 맞추어 한글 폰트를 설정합니다."""
    # macOS 기본 고딕체인 AppleGothic 적용
    plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams['axes.unicode_minus'] = False

def draw_pitch_chart(csv_path, pitcher_name, out_dir):
    """지정한 투수의 투구 분포 시각화 차트를 그립니다."""
    if not os.path.exists(csv_path):
        print(f"❌ 데이터셋 파일이 존재하지 않습니다: {csv_path}")
        print("   naver_kbo_pipeline.py를 먼저 실행해 주세요.")
        return
        
    df = pd.read_csv(csv_path)
    
    # 1. 투수 데이터 필터링 (결측치 제외)
    p_df = df[(df["pitcher_name"] == pitcher_name) & (df["plate_x"].notnull()) & (df["plate_z"].notnull())].copy()
    
    if p_df.empty:
        print(f"⚠️ {pitcher_name} 투수의 투구 데이터가 없습니다.")
        # 현재 데이터셋에 있는 투수 목록 추천 출력
        available_pitchers = df["pitcher_name"].dropna().unique()
        print(f"ℹ️ 시각화 가능한 투수 목록 (상위 10명): {', '.join(available_pitchers[:10])}")
        return
        
    print(f"🎯 {pitcher_name} 투수의 투구 레코드 {len(p_df)}건을 분석합니다.")
    
    # 2. 스트라이크 존 상하한선 평균값 계산
    # 만약 sz_top/sz_bottom 정보가 없으면 표준 규격인 3.4ft, 1.6ft 적용
    sz_top = p_df["sz_top"].mean() if p_df["sz_top"].notnull().any() else 3.4
    sz_bottom = p_df["sz_bottom"].mean() if p_df["sz_bottom"].notnull().any() else 1.6
    
    # 3. 차트 크기 및 테마 설정
    plt.figure(figsize=(8, 9))
    sns.set_theme(style="whitegrid")
    set_korean_font()
    
    # 4. 스트라이크 존 박스 드로잉
    # 홈플레이트 가로 너비: 17인치 = 약 1.417 ft => 좌우 범위는 -0.7083 ft ~ 0.7083 ft
    plate_width_limit = 0.7083
    
    # 외곽 스트라이크 존 사각형 (회색 실선)
    plt.plot([-plate_width_limit, plate_width_limit], [sz_top, sz_top], color="gray", linewidth=2.5, linestyle="-")
    plt.plot([-plate_width_limit, plate_width_limit], [sz_bottom, sz_bottom], color="gray", linewidth=2.5, linestyle="-")
    plt.plot([-plate_width_limit, -plate_width_limit], [sz_bottom, sz_top], color="gray", linewidth=2.5, linestyle="-")
    plt.plot([plate_width_limit, plate_width_limit], [sz_bottom, sz_top], color="gray", linewidth=2.5, linestyle="-")
    
    # 스트라이크 존 내부 9분할 가이드 라인 (회색 점선)
    x_split = plate_width_limit / 3
    y_split = (sz_top - sz_bottom) / 3
    
    # 세로 9분할 선
    plt.plot([-x_split, -x_split], [sz_bottom, sz_top], color="lightgray", linestyle="--", linewidth=1.2)
    plt.plot([x_split, x_split], [sz_bottom, sz_top], color="lightgray", linestyle="--", linewidth=1.2)
    # 가로 9분할 선
    plt.plot([-plate_width_limit, plate_width_limit], [sz_bottom + y_split, sz_bottom + y_split], color="lightgray", linestyle="--", linewidth=1.2)
    plt.plot([-plate_width_limit, plate_width_limit], [sz_bottom + 2 * y_split, sz_bottom + 2 * y_split], color="lightgray", linestyle="--", linewidth=1.2)
    
    # 5. 투구 산점도 플롯 (구종별 색상 분기 & 투구 결과 마커 분기)
    # 스트라이크 결과 계열은 원(o), 볼/타격 결과 계열은 X(x)로 표시하여 시각화 정보량 강화
    p_df["marker"] = p_df["pitch_result"].apply(lambda r: "o" if "스트라이크" in str(r) or "헛스윙" in str(r) or "루킹" in str(r) else "X")
    
    # 구종 종류에 맞춰 다채롭고 조화로운 팔레트 사용
    unique_pitches = p_df["pitch_type"].dropna().unique()
    colors = sns.color_palette("husl", len(unique_pitches))
    pitch_color_map = dict(zip(unique_pitches, colors))
    
    for pitch_type in unique_pitches:
        sub_df = p_df[p_df["pitch_type"] == pitch_type]
        
        # 스트라이크 마커 (o)
        strike_df = sub_df[sub_df["marker"] == "o"]
        if not strike_df.empty:
            plt.scatter(
                strike_df["plate_x"], strike_df["plate_z"],
                color=pitch_color_map[pitch_type], marker="o", s=130, edgecolors="black", linewidths=1.2,
                label=f"{pitch_type} (S)"
            )
            
        # 볼/기타 마커 (x)
        ball_df = sub_df[sub_df["marker"] == "X"]
        if not ball_df.empty:
            plt.scatter(
                ball_df["plate_x"], ball_df["plate_z"],
                color=pitch_color_map[pitch_type], marker="x", s=110, linewidths=2.5,
                label=f"{pitch_type} (B/H)"
            )
            
    # 6. 홈플레이트 하단 오각 형상 시각화 (포수 시점 가이드)
    plt.plot([-plate_width_limit, plate_width_limit], [0, 0], color="black", linewidth=2)
    plt.plot([-plate_width_limit, -plate_width_limit], [0, -0.15], color="black", linewidth=2)
    plt.plot([plate_width_limit, plate_width_limit], [0, -0.15], color="black", linewidth=2)
    plt.plot([-plate_width_limit, 0], [-0.15, -0.3], color="black", linewidth=2)
    plt.plot([plate_width_limit, 0], [-0.15, -0.3], color="black", linewidth=2)
    
    # 7. 축 한계값 및 레이아웃 조정
    plt.xlim(-2.2, 2.2)
    plt.ylim(-0.8, 5.0)
    plt.gca().set_aspect('equal', adjustable='box')
    
    # 라벨 및 텍스트 설정
    plt.title(f"KBO PTS 피치 트래커 - {pitcher_name} 투수 투구 분포\n(포수/심판 시점 View)", fontsize=16, fontweight="bold", pad=15)
    plt.xlabel("좌우 통과 위치 plate_x (ft)", fontsize=12)
    plt.ylabel("높이 통과 위치 plate_z (ft)", fontsize=12)
    
    # 중복 방지를 제거한 고유 범례 설정 (Legend)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc="upper right", frameon=True, shadow=True, fontsize=10)
    
    # 8. 저장 및 확인
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{pitcher_name}_pitch_chart.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    
    print(f"✅ 피칭 분포 시각화 완료! 차트 저장 경로:")
    print(f"   -> {os.path.abspath(out_path)}")

def main():
    parser = argparse.ArgumentParser(description="KBO PTS 투수 피칭 존 시각화 도구")
    parser.add_argument("--pitcher", type=str, default="주현상", help="시각화할 투수 이름 (기본값: 주현상)")
    args = parser.parse_args()
    
    csv_path = "./kbo_data/kbo_pitch_dataset.csv"
    out_dir = "./kbo_data"
    
    draw_pitch_chart(csv_path, args.pitcher, out_dir)

if __name__ == "__main__":
    main()
