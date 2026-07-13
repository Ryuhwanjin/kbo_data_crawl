import os
import json
import glob
import pandas as pd

def parse_sabermetrics_for_year(year, base_dir="kbo_data"):
    """
    특정 연도의 JSON 데이터만 읽어 타자/투수의 세이버메트릭스 지표를 산출합니다.
    """
    # 보정치 JSON 로드
    adjustments = {'batters': {}, 'pitchers': {}}
    adj_file = f"saber_data/adjustments_{year}.json"
    if os.path.exists(adj_file):
        with open(adj_file, "r", encoding="utf-8") as f:
            try:
                adjustments = json.load(f)
            except Exception as e:
                print(f"[WARNING] [{year}] 보정치 JSON 로드 실패: {e}")

    # [스킵 로직 비활성화] 다른 연도 일괄 재생성을 위해 항상 파싱을 진행합니다.

    target_dir = os.path.join(base_dir, str(year))
    files = []
    if os.path.exists(target_dir):
        for root, _, filenames in os.walk(target_dir):
            for fn in filenames:
                if fn.endswith('.json'):
                    files.append(os.path.join(root, fn))
    
    if not files:
        print(f"[{year}] 데이터 파일을 찾을 수 없습니다. (경로: {target_dir})")
        return
        
    print(f"[{year}] {len(files)}개의 게임 데이터 세이버메트릭스 분석 시작...")
    
    batters = {}
    pitchers = {}
    player_names = {}
    player_teams = {}
    
    for idx, fpath in enumerate(files):
        if (idx + 1) % 50 == 0:
            print(f"🔄 [{year}] 파일 파싱 진행 중: [{idx + 1}/{len(files)}] ({(idx+1)/len(files)*100:.1f}%)", flush=True)
            
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                continue
        
        # gameId 파싱 및 Lineup Roster 기반 이름/소속 팀 매핑 수집
        text_relay_data = data.get("result", {}).get("textRelayData", {})
        game_id = text_relay_data.get("gameId", "")
        
        team_code_map = {
            'WO': '키움', 'OB': '두산', 'SS': '삼성', 'HT': 'KIA', 'LT': '롯데',
            'SK': 'SSG', 'WY': 'SSG', 'KT': 'KT', 'NC': 'NC', 'HH': '한화', 'LG': 'LG'
        }
        
        away_team = "Unknown"
        home_team = "Unknown"
        if len(game_id) >= 12:
            away_code = game_id[8:10]
            home_code = game_id[10:12]
            away_team = team_code_map.get(away_code, "Unknown")
            home_team = team_code_map.get(home_code, "Unknown")
            
        for role in ["homeLineup", "awayLineup"]:
            lineup = text_relay_data.get(role, {})
            team_name = home_team if role == "homeLineup" else away_team
            if lineup:
                for player_type in ["batter", "pitcher"]:
                    for p in lineup.get(player_type, []):
                        if p.get("pcode") and p.get("name"):
                            player_names[str(p["pcode"])] = p["name"]
                            player_teams[str(p["pcode"])] = team_name
                            
        relays = text_relay_data.get("textRelays", [])
        if not relays:
            continue
            
        for relay in relays:
            text_options = relay.get("textOptions", [])
            current_batter = "Unknown"
            
            # 해당 타석(relay)에 병살이 기록되었는지 확인 (이중 카운팅 방지)
            has_double_play = False
            for opt in text_options:
                if "병살" in str(opt.get("text", "")):
                    has_double_play = True
                    break
            
            for opt in text_options:
                # [비디오 판독 아웃] 판독 번복으로 세이프가 아웃이 된 상황 처리
                if opt.get("type") == 7:
                    raw_text = str(opt.get("text", ""))
                    text = raw_text.replace(" ", "")
                    p_name = opt.get("currentGameState", {}).get("pitcher", "Unknown")
                    if p_name != "Unknown":
                        if p_name not in pitchers:
                            pitchers[p_name] = {'Outs': 0, 'H': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0, 'PA': 0}
                        if "세이프->아웃" in text or "세이프에서아웃" in text or "아웃으로번복" in text:
                            pitchers[p_name]['Outs'] += 1

                # [주자 아웃] 견제사, 도루실패 등 타석 결과와 무관하게 아웃카운트가 올라가는 주자 아웃 처리
                if opt.get("type") == 14:
                    raw_text = str(opt.get("text", ""))
                    text = raw_text.replace(" ", "")
                    p_name = opt.get("currentGameState", {}).get("pitcher", "Unknown")
                    if p_name != "Unknown":
                        if p_name not in pitchers:
                            pitchers[p_name] = {'Outs': 0, 'H': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0, 'PA': 0}
                        if "견제사" in text or "도루실패" in text or "도루자" in text:
                            pitchers[p_name]['Outs'] += 1
                        elif ("태그아웃" in text or "주루사" in text or "포스아웃" in text or "아웃" in text) and not has_double_play:
                            if "세이프" not in text and "진루" not in text:
                                pitchers[p_name]['Outs'] += 1

                current_pos = "지명타자"
                if opt.get("type") == 8 and opt.get("batterRecord"):
                    current_batter = opt["batterRecord"].get("name", current_batter)
                    current_pos = opt["batterRecord"].get("posName", "지명타자")
                    
                # 타입 13 (타석 결과) 또는 타입 23 (홈런) 에 대해서만 세이버메트릭스 누적
                if opt.get("type") in [13, 23]:
                    raw_text = str(opt.get("text", ""))
                    text = raw_text.replace(" ", "")
                    
                    b_name = current_batter
                    if ":" in raw_text:
                        b_name = raw_text.split(":")[0].strip()
                        
                    p_name = opt.get("currentGameState", {}).get("pitcher", "Unknown")
                    b_pcode = opt.get("currentGameState", {}).get("batter", "Unknown")
                    if not b_name or p_name == "Unknown": continue
                    
                    b_key = b_pcode if b_pcode != "Unknown" else b_name
                    
                    if b_key not in batters:
                        batters[b_key] = {
                            'pcode': b_pcode, 'name': b_name, 'PA': 0, 'AB': 0, 
                            '1B': 0, '2B': 0, '3B': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0,
                            'positions': {}
                        }
                    else:
                        if batters[b_key]['pcode'] == "Unknown" and b_pcode != "Unknown":
                            batters[b_key]['pcode'] = b_pcode
                        if b_name != "Unknown" and (batters[b_key]['name'] == "Unknown" or batters[b_key]['name'] != b_name):
                            batters[b_key]['name'] = b_name
                            
                    if p_name not in pitchers:
                        pitchers[p_name] = {'Outs': 0, 'H': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0, 'PA': 0}
                    
                    batters[b_key]['PA'] += 1
                    pitchers[p_name]['PA'] += 1
                    
                    # 포지션 누적 (대타, 대주자는 수비포지션이 아니므로 스킵)
                    if 'current_pos' in locals() and current_pos and current_pos not in ["대타", "대주자", "Unknown", ""]:
                        batters[b_key]['positions'][current_pos] = batters[b_key]['positions'].get(current_pos, 0) + 1
                    
                    is_ab = True
                    
                    # 결과 텍스트 정교한 키워드 파싱 로직 (예외 케이스 완벽 방어)
                    if "홈런" in text:
                        batters[b_key]['HR'] += 1
                        pitchers[p_name]['H'] += 1
                        pitchers[p_name]['HR'] += 1
                    elif "3루타" in text:
                        batters[b_key]['3B'] += 1
                        pitchers[p_name]['H'] += 1
                    elif "2루타" in text:
                        batters[b_key]['2B'] += 1
                        pitchers[p_name]['H'] += 1
                    elif ("1루타" in text or "안타" in text or "내야안타" in text) and "무안타" not in text and "실책" not in text:
                        # [노이즈 방어] 안타성 타구 아웃/잡힘 예외 차단
                        if any(x in text for x in ["아웃", "잡혔", "플라이", "뜬공", "땅볼", "직격아웃"]):
                            pitchers[p_name]['Outs'] += 1
                        else:
                            batters[b_key]['1B'] += 1
                            pitchers[p_name]['H'] += 1
                    elif "볼넷" in text or "고의4구" in text or "고의사구" in text:
                        batters[b_key]['BB'] += 1
                        pitchers[p_name]['BB'] += 1
                        is_ab = False
                    elif "몸에맞" in text or "사구" in text:
                        batters[b_key]['HBP'] += 1
                        pitchers[p_name]['HBP'] += 1
                        is_ab = False
                    elif any(x in text for x in ["삼진", "낫아웃", "루킹", "헛스윙", "스트라이크아웃", "스윙아웃"]):
                        batters[b_key]['SO'] += 1
                        pitchers[p_name]['SO'] += 1
                        pitchers[p_name]['Outs'] += 1
                        if "출루" in text or "폭투" in text or "포일" in text:
                            pitchers[p_name]['Outs'] -= 1 
                    elif "희생" in text:
                        is_ab = False
                        pitchers[p_name]['Outs'] += 1
                    elif "방해" in text:
                        is_ab = False
                    elif "병살" in text:
                        pitchers[p_name]['Outs'] += 2
                    elif "실책" in text or "야수선택" in text or "출루" in text:
                        pass
                    elif "아웃" in text or "땅볼" in text or "뜬공" in text or "플라이" in text or "파울" in text:
                        pitchers[p_name]['Outs'] += 1
                        
                    if is_ab:
                        batters[b_key]['AB'] += 1
                    
    # player_names를 역색인 (이름 -> pcode 리스트)
    name_to_pcodes = {}
    for code, nm in player_names.items():
        name_to_pcodes.setdefault(nm, []).append(code)
        
    # pcode가 Unknown이어서 이름(b_key)으로 임시 저장된 딕셔너리를 실제 pcode가 있는 딕셔너리로 병합
    resolved_batters = {}
    for key, st in batters.items():
        if st['pcode'] == "Unknown" or pd.isna(st['pcode']):
            candidates = name_to_pcodes.get(key, [])
            if len(candidates) == 1:
                real_pcode = candidates[0]
                st['pcode'] = real_pcode
                # 병합
                if real_pcode in resolved_batters:
                    for stat in ['PA', 'AB', '1B', '2B', '3B', 'HR', 'BB', 'HBP', 'SO']:
                        resolved_batters[real_pcode][stat] += st[stat]
                else:
                    resolved_batters[real_pcode] = st
                continue
        # 이미 pcode가 key인 경우
        if key in resolved_batters:
            for stat in ['PA', 'AB', '1B', '2B', '3B', 'HR', 'BB', 'HBP', 'SO']:
                resolved_batters[key][stat] += st[stat]
        else:
            resolved_batters[key] = st
            
    batters = resolved_batters

    # 타자 지표 가공
    b_result = []
    max_pa = 0
    for b_key, st in batters.items():
        if st['PA'] > max_pa: max_pa = st['PA']
        # 보정치 적용
        pcode_str = str(int(st['pcode'])) if st.get('pcode') not in (None, 'Unknown') else 'Unknown'
        if pcode_str in adjustments['batters']:
            for stat, val in adjustments['batters'][pcode_str].items():
                st[stat] += val
        if st['PA'] < 10: continue
        
        woba = (0.69*st['BB'] + 0.72*st['HBP'] + 0.89*st['1B'] + 1.27*st['2B'] + 1.62*st['3B'] + 2.10*st['HR']) / max(1, st['PA'])
        ab_val = max(1, st['AB'])
        slg = (st['1B']*1 + st['2B']*2 + st['3B']*3 + st['HR']*4) / ab_val
        avg = (st['1B'] + st['2B'] + st['3B'] + st['HR']) / ab_val
        iso = slg - avg
        
        name = player_names.get(str(st['pcode']), st['name'])
        
        # 주 포지션 결정
        pos_counts = st.get('positions', {})
        main_pos = "지명타자"
        if pos_counts:
            main_pos = max(pos_counts, key=pos_counts.get)
            
        b_result.append({
            'Player': name,
            'pcode': st.get('pcode', 'Unknown'),
            'Team': player_teams.get(str(st['pcode']), 'Unknown'),
            'Position': main_pos,
            'PA': st['PA'],
            'HR': st['HR'],
            'wOBA': round(woba, 3),
            'ISO': round(iso, 3),
            'BB%': round(st['BB'] / st['PA'] * 100, 1),
            'K%': round(st['SO'] / st['PA'] * 100, 1),
            'AB': st['AB'],
            '1B': st['1B'],
            '2B': st['2B'],
            '3B': st['3B'],
            'BB': st['BB'],
            'HBP': st['HBP'],
            'SO': st['SO']
        })
        
    # 투수 지표 가공 (FIP 등 및 클래식 스탯)
    p_result = []
    for pcode, st in pitchers.items():
        # 보정치 적용
        pcode_str = str(int(pcode)) if pcode not in (None, 'Unknown') else 'Unknown'
        if pcode_str in adjustments['pitchers']:
            for stat, val in adjustments['pitchers'][pcode_str].items():
                st[stat] += val
        ip = st['Outs'] / 3.0
        if ip < 3: continue
        
        fip = (13*st['HR'] + 3*(st['BB']+st['HBP']) - 2*st['SO']) / max(0.1, ip) + 3.20
        k9 = (st['SO'] * 9) / max(0.1, ip)
        bb9 = (st['BB'] * 9) / max(0.1, ip)
        
        name = player_names.get(str(pcode), "Unknown")
        p_result.append({
            'Player': name,
            'pcode': pcode,
            'Team': player_teams.get(str(pcode), 'Unknown'),
            'IP': st['Outs'] // 3 + (st['Outs'] % 3) / 10.0,
            'Outs': st['Outs'],
            'H': st['H'],
            'HR': st['HR'],
            'BB': st['BB'],
            'HBP': st['HBP'],
            'SO': st['SO'],
            'FIP': round(fip, 2),
            'K/9': round(k9, 2),
            'BB/9': round(bb9, 2)
        })
        
        
    df_batters = pd.DataFrame(b_result)
    if not df_batters.empty:
        df_batters = df_batters.sort_values('wOBA', ascending=False)
        
    df_pitchers = pd.DataFrame(p_result)
    if not df_pitchers.empty:
        df_pitchers = df_pitchers.sort_values('FIP', ascending=True)
    
    print(f"[DEBUG] 스캔 완료. 가장 많은 타석(PA)을 소화한 타자의 타석 수: {max_pa}")
    
    # CSV 저장
    if not df_batters.empty:
        df_batters.to_csv(f"kbo_batter_saber_{year}.csv", index=False, encoding='utf-8-sig')
        os.makedirs("saber_data", exist_ok=True)
        df_batters.to_csv(f"saber_data/kbo_batter_saber_{year}.csv", index=False, encoding='utf-8-sig')
    if not df_pitchers.empty:
        df_pitchers.to_csv(f"kbo_pitcher_saber_{year}.csv", index=False, encoding='utf-8-sig')
        os.makedirs("saber_data", exist_ok=True)
        df_pitchers.to_csv(f"saber_data/kbo_pitcher_saber_{year}.csv", index=False, encoding='utf-8-sig')
    
    print("=" * 50)
    print(f"[{year}] 타자 Top 5 wOBA (최소 10타석):")
    print(df_batters.head(5).to_string(index=False) if not df_batters.empty else "데이터 없음")
    print("-" * 50)
    print(f"[{year}] 투수 Top 5 FIP (최소 3이닝):")
    print(df_pitchers.head(5).to_string(index=False) if not df_pitchers.empty else "데이터 없음")
    print("=" * 50)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True, help='파싱할 연도 (예: 2017)')
    args = parser.parse_args()
    
    parse_sabermetrics_for_year(args.year)
