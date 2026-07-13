import os
import sys
import argparse
import pandas as pd
import numpy as np

def calculate_war_for_year(year):
    bat_path = f"saber_data/kbo_batter_saber_{year}.csv"
    pit_path = f"saber_data/kbo_pitcher_saber_{year}.csv"
    
    if not os.path.exists(bat_path) or not os.path.exists(pit_path):
        print(f"⚠️ [{year}] 타자 또는 투수 CSV 파일이 존재하지 않아 WAR 계산을 스킵합니다.")
        return
        
    df_bat = pd.read_csv(bat_path)
    df_pit = pd.read_csv(pit_path)
    
    print(f"⚾ [{year}년] 세이버메트릭스 WAR 계산 엔진 가동...")
    
    # -------------------------------------------------------------
    # 1. 타자 WAR 계산
    # -------------------------------------------------------------
    # 리그 전체 타자 누적값
    total_pa = df_bat['PA'].sum()
    total_ab = df_bat['AB'].sum()
    total_bb = df_bat['BB'].sum()
    total_hbp = df_bat['HBP'].sum()
    total_1b = df_bat['1B'].sum()
    total_2b = df_bat['2B'].sum()
    total_3b = df_bat['3B'].sum()
    total_hr = df_bat['HR'].sum()
    
    # 리그 평균 wOBA 동적 연산
    league_woba = (0.69*total_bb + 0.72*total_hbp + 0.89*total_1b + 1.27*total_2b + 1.62*total_3b + 2.10*total_hr) / max(1, total_pa)
    # wOBA Scale 표준 상수 설정
    woba_scale = 1.15
    
    # KBO 포지션 조정값 (144경기 기준 Runs)
    # 포수: +9.0, 유격수: +7.5, 2루수: +3.0, 3루수: +0.75, 중견수: +2.5, 좌/우익수: -7.5, 1루수: -12.5, 지명타자: -17.5
    pos_adjustments = {
        '포수': 9.0,
        '유격수': 7.5,
        '2루수': 3.0,
        '3루수': 0.75,
        '중견수': 2.5,
        '좌익수': -7.5,
        '우익수': -7.5,
        '외야수': -7.5,
        '1루수': -12.5,
        '지명타자': -17.5,
        '내야수': -12.5,
        'Unknown': -15.0
    }
    
    bat_wars = []
    for idx, row in df_bat.iterrows():
        pa = max(1, row['PA'])
        ab = max(1, row['AB'])
        
        # 개인 wOBA 및 wRAA 연산
        woba = (0.69*row['BB'] + 0.72*row['HBP'] + 0.89*row['1B'] + 1.27*row['2B'] + 1.62*row['3B'] + 2.10*row['HR']) / pa
        wraa = ((woba - league_woba) / woba_scale) * pa
        
        # 조정 wRC+ 연산 (리그 평균 대비 득점 생산율)
        # KBO 리그 평균 타석당 득점율 (약 0.12 Runs로 표준 보정)
        lg_run_per_pa = 0.12
        wrc_plus = ((wraa / pa + lg_run_per_pa) / lg_run_per_pa) * 100
        wrc_plus = max(0.0, min(300.0, wrc_plus)) # 극단적인 이상치 제한
        
        # 포지션 조정값 반영 (선수의 타석 비율에 비례하도록 조정)
        pos_name = str(row.get('Position', '지명타자')).strip()
        pos_val = pos_adjustments.get(pos_name, -15.0)
        # 144경기(약 600타석) 기준 포지션 조정 환산
        pos_runs = pos_val * (pa / 600.0)
        
        # 대체선수 수준 보정 (평균 대비 약 -20% 득점 감쇄, 타석당 0.03 Runs 보정)
        rep_runs = pa * 0.03
        
        # RAR 및 최종 WAR
        rar = wraa + pos_runs + rep_runs
        war = rar / 10.0 # KBO 표준 10득점당 1승 환산
        
        bat_wars.append({
            'wRC+': round(wrc_plus, 1),
            'wRAA': round(wraa, 2),
            'WAR': round(war, 2)
        })
        
    df_bat_war = pd.DataFrame(bat_wars)
    
    # 기존 CSV에 컬럼 결합 및 덮어쓰기
    df_bat['wRC+'] = df_bat_war['wRC+']
    df_bat['wRAA'] = df_bat_war['wRAA']
    df_bat['WAR'] = df_bat_war['WAR']
    
    # 내림차순 정렬하여 저장
    df_bat = df_bat.sort_values('WAR', ascending=False)
    df_bat.to_csv(bat_path, index=False, encoding='utf-8-sig')
    if os.path.exists(f"saber_data/kbo_batter_saber_{year}.csv"):
        df_bat.to_csv(f"kbo_batter_saber_{year}.csv", index=False, encoding='utf-8-sig')
    
    # -------------------------------------------------------------
    # 2. 투수 WAR 계산 (FIP 기반)
    # -------------------------------------------------------------
    total_ip = df_pit['IP'].sum()
    total_hr_p = df_pit['HR'].sum()
    total_bb_p = df_pit['BB'].sum()
    total_hbp_p = df_pit['HBP'].sum()
    total_so_p = df_pit['SO'].sum()
    
    # 리그 평균 FIP 상수 연산 (KBO 리그 평균자책점 평균을 4.50 수준으로 보정)
    league_era = 4.50
    fip_const = league_era - (13*total_hr_p + 3*(total_bb_p+total_hbp_p) - 2*total_so_p) / max(0.1, total_ip)
    
    pit_wars = []
    for idx, row in df_pit.iterrows():
        ip = max(0.1, row['IP'])
        # 실제 이닝 수(float)로 아웃카운트 기준 변환하여 WAR 계산
        outs = row['Outs']
        ip_float = outs / 3.0
        
        # 개인 FIP 연산
        fip = (13*row['HR'] + 3*(row['BB']+row['HBP']) - 2*row['SO']) / max(0.1, ip_float) + fip_const
        fip = max(0.0, fip)
        
        # 대체선수 FIP (대체 수준 투수는 리그 평균 FIP 대비 1.25 Runs 높게 설정)
        rep_fip = league_era + 1.25
        
        # 득점 방지 기여 (Runs Saved)
        # FIP에 기반한 평균 대비 득점 절감액 환산
        runs_prevented = (rep_fip - fip) * (ip_float / 9.0)
        
        # WAR (10득점당 1승)
        war = runs_prevented / 10.0
        
        pit_wars.append({
            'WAR': round(war, 2)
        })
        
    df_pit_war = pd.DataFrame(pit_wars)
    
    # 투수 CSV에 결합 및 덮어쓰기
    df_pit['WAR'] = df_pit_war['WAR']
    
    # 내림차순 정렬하여 저장
    df_pit = df_pit.sort_values('WAR', ascending=False)
    df_pit.to_csv(pit_path, index=False, encoding='utf-8-sig')
    if os.path.exists(f"saber_data/kbo_pitcher_saber_{year}.csv"):
        df_pit.to_csv(f"kbo_pitcher_saber_{year}.csv", index=False, encoding='utf-8-sig')
        
    print(f"📊 [{year}년] WAR 지표 갱신 완료! (최고 타자: {df_bat.iloc[0]['Player']} WAR {df_bat.iloc[0]['WAR']}, 최고 투수: {df_pit.iloc[0]['Player']} WAR {df_pit.iloc[0]['WAR']})")

def main():
    parser = argparse.ArgumentParser(description="KBO 타자/투수 세이버메트릭스 WAR(승리 기여도)를 동적 리그 스케일로 연산합니다.")
    parser.add_argument('--year', type=int, default=2026, help="WAR를 계산할 시즌 연도 (기본값: 2026)")
    args = parser.parse_args()
    
    calculate_war_for_year(args.year)

if __name__ == "__main__":
    main()
