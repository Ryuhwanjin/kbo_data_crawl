import os
import re
import pandas as pd

def naver_ip_to_outs(ip_str):
    ip_str = ip_str.strip()
    if not ip_str:
        return 0
    try:
        if ' ' in ip_str:
            parts = ip_str.split(' ')
            integer_part = int(parts[0])
            fraction_part = parts[1]
            if fraction_part == '1/3':
                outs = integer_part * 3 + 1
            elif fraction_part == '2/3':
                outs = integer_part * 3 + 2
            else:
                outs = integer_part * 3
        elif '/' in ip_str:
            if ip_str == '1/3':
                outs = 1
            elif ip_str == '2/3':
                outs = 2
            else:
                outs = 0
        else:
            if '.' in ip_str:
                parts = ip_str.split('.')
                integer_part = int(parts[0])
                fraction_part = int(parts[1])
                outs = integer_part * 3 + fraction_part
            else:
                outs = int(ip_str) * 3
        return outs
    except:
        return 0

def ip_diff_str_to_outs(diff_str):
    # diff_str: "+0.1", "-1.0", "0.2" 등
    diff_str = diff_str.strip()
    sign = 1
    if diff_str.startswith("-"):
        sign = -1
        diff_str = diff_str[1:]
    elif diff_str.startswith("+"):
        diff_str = diff_str[1:]
        
    parts = diff_str.split('.')
    if len(parts) == 2:
        integer_diff = int(parts[0])
        fraction_diff = int(parts[1])
        outs = integer_diff * 3 + fraction_diff
    else:
        outs = int(diff_str) * 3
        
    return sign * outs

def run_local_validation(year, player_type="batter"):
    log_file = f'logs/validation_errors_{player_type}_{year}.log'
    old_csv = f'saber_data/kbo_{player_type}_saber_{year}_old.csv'
    new_csv = f'saber_data/kbo_{player_type}_saber_{year}.csv'
    
    if not os.path.exists(log_file) or not os.path.exists(old_csv) or not os.path.exists(new_csv):
        return
        
    df_old = pd.read_csv(old_csv).set_index('Player')
    df_new = pd.read_csv(new_csv).set_index('Player')
    
    # 1. 이전 로그에서 오차 내역 파싱
    player_errors = {}
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if "오차 발생:" in line:
                match = re.search(r"\[(.*?)\] 오차 발생: (.*)", line)
                if match:
                    player = match.group(1)
                    err_details = match.group(2).strip()
                    player_errors[player] = err_details
                    
    if not player_errors:
        print(f"[{year}년] [{player_type}] 기존 오차가 없거나 로그가 비어 있습니다. (정합성 100%)")
        return
        
    print(f"\n=== [{year}년] [{player_type}] 초고속 로컬 검증 시작 (기존 오차 대상자: {len(player_errors)}명) ===")
    
    solved_count = 0
    remaining_count = 0
    
    for player, err_str in player_errors.items():
        if player not in df_old.index or player not in df_new.index:
            print(f"⏩ [{player}] 구버전/신버전 CSV 데이터 누락으로 스킵")
            continue
            
        old_row = df_old.loc[player]
        new_row = df_new.loc[player]
        
        # 여러 행이 잡힐 경우 첫 번째 행 선택
        if isinstance(old_row, pd.DataFrame): old_row = old_row.iloc[0]
        if isinstance(new_row, pd.DataFrame): new_row = new_row.iloc[0]
        
        # 오차 항목들 분해 및 네이버 정답값 역산
        diffs = err_str.split(", ")
        all_resolved = True
        resolved_details = []
        unresolved_details = []
        
        for diff in diffs:
            parts = diff.split(" ")
            if len(parts) < 2: continue
            stat = parts[0]
            val_str = parts[1] # "+1", "-2" 등
            
            # 구버전 성적
            if stat == 'IP':
                old_outs = int(old_row['Outs'])
                new_outs = int(new_row['Outs'])
                diff_outs = ip_diff_str_to_outs(val_str)
                naver_outs = old_outs + diff_outs
                
                if new_outs == naver_outs:
                    resolved_details.append(f"IP({old_outs // 3}.{old_outs % 3} -> {new_outs // 3}.{new_outs % 3} == 네이버 {naver_outs // 3}.{naver_outs % 3})")
                else:
                    all_resolved = False
                    curr_diff = naver_outs - new_outs
                    sign = "+" if curr_diff > 0 else ""
                    unresolved_details.append(f"IP(네이버 {naver_outs // 3}.{naver_outs % 3} != 현재 {new_outs // 3}.{new_outs % 3} [오차 {sign}{curr_diff/3:.1f}])")
            else:
                # 일반 스탯
                # 구버전 CSV 상의 스탯 구하기
                if player_type == "batter":
                    if stat == 'H':
                        old_val = int(old_row['1B']) + int(old_row['2B']) + int(old_row['3B']) + int(old_row['HR'])
                        new_val = int(new_row['1B']) + int(new_row['2B']) + int(new_row['3B']) + int(new_row['HR'])
                    else:
                        old_val = int(old_row[stat])
                        new_val = int(new_row[stat])
                else:
                    old_val = int(old_row[stat])
                    new_val = int(new_row[stat])
                    
                sign = 1
                clean_val_str = val_str
                if val_str.startswith("-"):
                    sign = -1
                    clean_val_str = val_str[1:]
                elif val_str.startswith("+"):
                    clean_val_str = val_str[1:]
                    
                diff_val = sign * int(clean_val_str)
                naver_val = old_val + diff_val
                
                if new_val == naver_val:
                    resolved_details.append(f"{stat}({old_val} -> {new_val} == 네이버 {naver_val})")
                else:
                    all_resolved = False
                    unresolved_details.append(f"{stat}(네이버 {naver_val} != 현재 {new_val})")
                    
        if all_resolved:
            solved_count += 1
            print(f"✅ [{player}] 오차 완벽 해결! ➡️ " + ", ".join(resolved_details))
        else:
            remaining_count += 1
            print(f"❌ [{player}] 오차 잔존! ➡️ " + ", ".join(unresolved_details))
            
    print(f"▶️ [{year}년] [{player_type}] 요약: 총 {len(player_errors)}명 중 {solved_count}명 해결 완료, {remaining_count}명 오차 잔존.")

if __name__ == "__main__":
    for year in range(2017, 2026):
        run_local_validation(year, "batter")
        run_local_validation(year, "pitcher")
