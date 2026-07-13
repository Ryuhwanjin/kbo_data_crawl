import os
import argparse
import random
import pandas as pd
import numpy as np

# KBO 구단 약명 통일 맵
TEAM_NAME_MAP = {
    '기아': 'KIA', 'KIA': 'KIA', 'kia': 'KIA',
    '삼성': '삼성', '라이온즈': '삼성',
    '엘지': 'LG', 'LG': 'LG', 'lg': 'LG',
    '두산': '두산', '베어스': '두산',
    '에스에스지': 'SSG', 'SSG': 'SSG', 'ssg': 'SSG', '쓱': 'SSG',
    '케이티': 'KT', 'KT': 'KT', 'kt': 'KT',
    '롯데': '롯데', '자이언츠': '롯데',
    '한화': '한화', '이글스': '한화',
    '엔씨': 'NC', 'NC': 'NC', 'nc': 'NC',
    '키움': '키움', '히어로즈': '키움'
}

def load_roster_data(year=2026):
    bat_path = f"saber_data/kbo_batter_saber_{year}.csv"
    pit_path = f"saber_data/kbo_pitcher_saber_{year}.csv"
    
    if not os.path.exists(bat_path) or not os.path.exists(pit_path):
        raise FileNotFoundError(f"⚠️ [{year}] 정밀 파이프라인 CSV 데이터가 존재하지 않습니다. 먼저 updater를 돌려주세요.")
        
    df_bat = pd.read_csv(bat_path)
    df_pit = pd.read_csv(pit_path)
    return df_bat, df_pit

# 타자-투수 대결 결과 결정 (Log-Odds 융합 모델)
def simulate_at_bat(batter, pitcher, league_avgs):
    # 타자의 각 이벤트 발생 확률
    b_pa = max(1, batter['PA'])
    b_bb = (batter['BB'] + batter['HBP']) / b_pa
    b_so = batter['SO'] / b_pa
    b_hr = batter['HR'] / b_pa
    b_h = (batter['1B'] + batter['2B'] + batter['3B'] + batter['HR']) / b_pa
    b_1b = batter['1B'] / b_pa
    b_2b = batter['2B'] / b_pa
    b_3b = batter['3B'] / b_pa
    
    # 투수의 피이벤트 발생 확률
    p_outs = max(1, pitcher['Outs'])
    p_pa = pitcher.get('PA', p_outs + pitcher['H'] + pitcher['BB'] + pitcher['HBP'])
    p_pa = max(1, p_pa)
    p_bb = (pitcher['BB'] + pitcher['HBP']) / p_pa
    p_so = pitcher['SO'] / p_pa
    p_hr = pitcher['HR'] / p_pa
    p_h = pitcher['H'] / p_pa
    
    # 리그 평균값
    l_bb = league_avgs['BB']
    l_so = league_avgs['SO']
    l_hr = league_avgs['HR']
    l_h = league_avgs['H']
    
    # Log-Odds 결합 공식 (Bill James Odds Formula)
    # P = (Batter * Pitcher / League) / [ (Batter * Pitcher / League) + ((1 - Batter) * (1 - Pitcher) / (1 - League)) ]
    def combine_odds(b_prob, p_prob, l_prob):
        b_prob = max(0.001, min(0.999, b_prob))
        p_prob = max(0.001, min(0.999, p_prob))
        l_prob = max(0.001, min(0.999, l_prob))
        
        num = (b_prob * p_prob) / l_prob
        den = num + ((1.0 - b_prob) * (1.0 - p_prob)) / (1.0 - l_prob)
        return num / max(0.0001, den)
        
    p_bb_final = combine_odds(b_bb, p_bb, l_bb)
    p_so_final = combine_odds(b_so, p_so, l_so)
    p_hr_final = combine_odds(b_hr, p_hr, l_hr)
    p_h_final = combine_odds(b_h, p_h, l_h)
    
    # 개별 안타 종류 결정 (타자 지분 적용)
    h_sum = max(0.0001, b_1b + b_2b + b_3b + b_hr)
    p_1b_final = p_h_final * (b_1b / h_sum)
    p_2b_final = p_h_final * (b_2b / h_sum)
    p_3b_final = p_h_final * (b_3b / h_sum)
    p_hr_final = p_h_final * (b_hr / h_sum)
    
    # 전체 아웃컴 누적 확률 구성
    # 1. 볼넷/사구, 2. 삼진, 3. 홈런, 4. 3루타, 5. 2루타, 6. 1루타, 7. 인플레이아웃
    probs = [
        p_bb_final,
        p_so_final,
        p_hr_final,
        p_3b_final,
        p_2b_final,
        p_1b_final
    ]
    
    sum_probs = sum(probs)
    if sum_probs > 0.95:
        # 확률 합이 1을 넘지 않도록 보정
        scale = 0.95 / sum_probs
        probs = [p * scale for p in probs]
        
    # 아웃 확률
    p_out_final = 1.0 - sum(probs)
    probs.append(p_out_final)
    
    # 0: 볼넷, 1: 삼진, 2: 홈런, 3: 3루타, 4: 2루타, 5: 1루타, 6: 인플레이아웃
    r = random.random()
    cumulative = 0.0
    for idx, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            return idx
    return 6

# 단일 이닝 시뮬레이션 (Base State transitions)
def play_half_inning(lineup, batter_idx, pitcher, league_avgs, is_bullpen=False):
    outs = 0
    runs = 0
    # 주자 상황: 0: 없음, 1: 있음
    bases = [0, 0, 0] # [1루, 2루, 3루]
    
    while outs < 3:
        batter = lineup[batter_idx]
        # 타석 결과 시뮬레이션
        outcome = simulate_at_bat(batter, pitcher, league_avgs)
        
        if outcome == 0: # 볼넷 / 사구
            if bases[0] == 0:
                bases[0] = 1
            elif bases[1] == 0:
                bases[1] = 1
            elif bases[2] == 0:
                bases[2] = 1
            else: # 밀어내기 득점
                runs += 1
        elif outcome == 1: # 삼진
            outs += 1
        elif outcome == 2: # 홈런
            runs += sum(bases) + 1
            bases = [0, 0, 0]
        elif outcome == 3: # 3루타
            runs += sum(bases)
            bases = [0, 0, 1]
        elif outcome == 4: # 2루타 (주자 2개 루 진루)
            runs += bases[1] + bases[2]
            bases[2] = bases[0] # 1루 주자는 3루로
            bases[1] = 1
            bases[0] = 0
        elif outcome == 5: # 1루타 (주자 2개 루 진루 표준 가정)
            runs += bases[1] + bases[2]
            bases[2] = bases[0] # 1루 주자 3루로
            bases[1] = 0
            bases[0] = 1
        else: # 인플레이 아웃
            outs += 1
            # 희생플라이 등의 가상 득점 반영 (3루 주자 아웃 시 30% 확률 득점)
            if outs < 3 and bases[2] == 1 and random.random() < 0.3:
                runs += 1
                bases[2] = 0
                
        batter_idx = (batter_idx + 1) % 9
        
    return runs, batter_idx

# 9이닝 풀 게임 시뮬레이션
def play_game(away_lineup, home_lineup, away_pitcher, home_pitcher, league_avgs, bullpen_pitcher):
    away_score = 0
    home_score = 0
    
    away_idx = 0
    home_idx = 0
    
    # 1이닝부터 9이닝까지 진행
    for inning in range(1, 10):
        # 선발투수 한계 투구수 고려 (6이닝 이후 불펜 투수로 자동 교체)
        current_away_pit = away_pitcher if inning <= 6 else bullpen_pitcher
        current_home_pit = home_pitcher if inning <= 6 else bullpen_pitcher
        
        # 초공격: 원정팀
        runs, away_idx = play_half_inning(away_lineup, away_idx, current_home_pit, league_avgs)
        away_score += runs
        
        # 9회말 홈팀이 이기고 있으면 말 공격 생략
        if inning == 9 and home_score > away_score:
            break
            
        # 말공격: 홈팀
        runs, home_idx = play_half_inning(home_lineup, home_idx, current_away_pit, league_avgs)
        home_score += runs
        
    # 9회말 종료 후 동점 시 최대 12회까지 연장 승부 진행
    if away_score == home_score:
        for inning in range(10, 13):
            # 연장 초공격
            runs, away_idx = play_half_inning(away_lineup, away_idx, bullpen_pitcher, league_avgs)
            away_score += runs
            
            # 연장 말공격
            runs, home_idx = play_half_inning(home_lineup, home_idx, bullpen_pitcher, league_avgs)
            home_score += runs
            
            if away_score != home_score:
                break
                
    return away_score, home_score

def run_monte_carlo(home_team, away_team, year=2026, sim_count=1000):
    df_bat, df_pit = load_roster_data(year)
    
    # 리그 평균 스탯 집계 (Log-Odds 분모용)
    tot_pa = df_bat['PA'].sum()
    league_avgs = {
        'BB': (df_bat['BB'].sum() + df_bat['HBP'].sum()) / tot_pa,
        'SO': df_bat['SO'].sum() / tot_pa,
        'HR': df_bat['HR'].sum() / tot_pa,
        'H': (df_bat['1B'].sum() + df_bat['2B'].sum() + df_bat['3B'].sum() + df_bat['HR'].sum()) / tot_pa
    }
    
    # 평균적인 불펜 투수 스탯 (선발 강판 후 교체용)
    bullpen_pitcher = {
        'Outs': 100 * 3, 'PA': 420,
        'H': 90, 'HR': 9, 'BB': 35, 'HBP': 4, 'SO': 80
    }
    
    # 팀 소속 타자/투수 분류
    home_batters = df_bat[df_bat['Team'] == home_team]
    away_batters = df_bat[df_bat['Team'] == away_team]
    home_pitchers = df_pit[df_pit['Team'] == home_team]
    away_pitchers = df_pit[df_pit['Team'] == away_team]
    
    if home_batters.empty or away_batters.empty:
        raise ValueError(f"❌ [{home_team}] 또는 [{away_team}] 팀 선수단 정보가 부족합니다. CSV 데이터를 확인해 주세요.")
        
    # 선발 라인업 구성 (wOBA 순위 상위 9명 배치)
    home_lineup = home_batters.sort_values('wOBA', ascending=False).head(9).to_dict('records')
    away_lineup = away_batters.sort_values('wOBA', ascending=False).head(9).to_dict('records')
    
    # 1선발 투수 선정 (이닝 수가 가장 많은 선수)
    home_p = home_pitchers.sort_values('Outs', ascending=False).iloc[0].to_dict()
    away_p = away_pitchers.sort_values('Outs', ascending=False).iloc[0].to_dict()
    
    print(f"\n📋 [{away_team}] 선발 라인업 (원정):")
    for i, b in enumerate(away_lineup):
        print(f"  {i+1}번. {b['Player']} ({b['Position']}, wOBA: {b['wOBA']:.3f}, WAR: {b['WAR']})")
    print(f"  선발 투수: {away_p['Player']} (FIP: {away_p['FIP']:.2f}, WAR: {away_p['WAR']})")
    
    print(f"\n📋 [{home_team}] 선발 라인업 (홈):")
    for i, b in enumerate(home_lineup):
        print(f"  {i+1}번. {b['Player']} ({b['Position']}, wOBA: {b['wOBA']:.3f}, WAR: {b['WAR']})")
    print(f"  선발 투수: {home_p['Player']} (FIP: {home_p['FIP']:.2f}, WAR: {home_p['WAR']})")
    
    print(f"\n🎲 몬테카를로 경기 시뮬레이션 {sim_count}회 가동 중...")
    
    home_wins = 0
    away_wins = 0
    ties = 0
    
    total_home_runs = 0
    total_away_runs = 0
    
    for _ in range(sim_count):
        a_score, h_score = play_game(away_lineup, home_lineup, away_p, home_p, league_avgs, bullpen_pitcher)
        total_away_runs += a_score
        total_home_runs += h_score
        
        if h_score > a_score:
            home_wins += 1
        elif a_score > h_score:
            away_wins += 1
        else:
            ties += 1
            
    print(f"\n==================================================")
    print(f"🔮 [예측 결과 보고서] {away_team} vs {home_team}")
    print(f"==================================================")
    print(f"🏆 {home_team} 승률: {home_wins / sim_count * 100:.1f}% ({home_wins}승)")
    print(f"🏆 {away_team} 승률: {away_wins / sim_count * 100:.1f}% ({away_wins}승)")
    if ties > 0:
        print(f"🤝 무승부 확률: {ties / sim_count * 100:.1f}% ({ties}무)")
    print(f"--------------------------------------------------")
    print(f"📈 평균 예상 득점: {away_team} {total_away_runs / sim_count:.1f} vs {home_team} {total_home_runs / sim_count:.1f}")
    print(f"==================================================")

def main():
    parser = argparse.ArgumentParser(description="KBO 두 팀 간 가상 시뮬레이션 승패 예측기")
    parser.add_argument('--home', type=str, required=True, help="홈팀 이름 (예: KIA, 삼성, LG, 두산, SSG, KT, 롯데, 한화, NC, 키움)")
    parser.add_argument('--away', type=str, required=True, help="원정팀 이름")
    parser.add_argument('--year', type=int, default=2026, help="스탯 기준 시즌 연도 (기본값: 2026)")
    parser.add_argument('--sims', type=int, default=1000, help="시뮬레이션 반복 횟수 (기본값: 1000)")
    args = parser.parse_args()
    
    h_team = TEAM_NAME_MAP.get(args.home)
    a_team = TEAM_NAME_MAP.get(args.away)
    
    if not h_team or not a_team:
        print(f"❌ 입력한 팀명이 올바르지 않습니다. (입력 홈: {args.home}, 원정: {args.away})")
        sys.exit(1)
        
    run_monte_carlo(h_team, a_team, args.year, args.sims)

if __name__ == "__main__":
    main()
