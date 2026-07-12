import os
import json
import glob
import pandas as pd

def parse_sabermetrics_for_year(year, base_dir="kbo_data"):
    """
    특정 연도의 JSON 데이터만 읽어 타자/투수의 세이버메트릭스 지표를 산출합니다.
    """
    # [스킵 로직] 이미 파싱된 CSV가 존재하면 무거운 JSON 파싱 과정을 통째로 건너뜁니다! (시간 절약)
    output_filename = f"kbo_batter_saber_{year}.csv"
    if os.path.exists(output_filename):
        print(f"⏩ [{year}] 이미 파싱 완료된 CSV({output_filename})가 존재하여 파싱 과정을 1초 만에 스킵합니다!")
        return

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
    
    for idx, fpath in enumerate(files):
        if (idx + 1) % 50 == 0:
            print(f"🔄 [{year}] 파일 파싱 진행 중: [{idx + 1}/{len(files)}] ({(idx+1)/len(files)*100:.1f}%)", flush=True)
            
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                continue
        
        # entry에서 이름 매핑 수집
        text_relay_data = data.get("result", {}).get("textRelayData", {})
        for entry_key in ["homeEntry", "awayEntry"]:
            entry = text_relay_data.get(entry_key, {})
            if entry:
                for role in ["batter", "pitcher"]:
                    for p in entry.get(role, []):
                        if p.get("pcode") and p.get("name"):
                            player_names[str(p["pcode"])] = p["name"]
                            
        relays = text_relay_data.get("textRelays", [])
        if not relays:
            continue
            
        for relay in relays:
            text_options = relay.get("textOptions", [])
            current_batter = "Unknown"
            
            for opt in text_options:
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

                if opt.get("type") == 8 and opt.get("batterRecord"):
                    current_batter = opt["batterRecord"].get("name", current_batter)
                    
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
                    
                    if b_name not in batters:
                        batters[b_name] = {'pcode': b_pcode, 'PA': 0, 'AB': 0, '1B': 0, '2B': 0, '3B': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0}
                    # pcode 업데이트 (처음에 못 잡았을 경우)
                    if b_pcode != "Unknown":
                        batters[b_name]['pcode'] = b_pcode
                        
                    if p_name not in pitchers:
                        pitchers[p_name] = {'Outs': 0, 'H': 0, 'HR': 0, 'BB': 0, 'HBP': 0, 'SO': 0, 'PA': 0}
                    
                    batters[b_name]['PA'] += 1
                    pitchers[p_name]['PA'] += 1
                    
                    is_ab = True
                    
                    # 결과 텍스트 정교한 키워드 파싱 로직 (예외 케이스 완벽 방어)
                    if "홈런" in text:
                        batters[b_name]['HR'] += 1
                        pitchers[p_name]['H'] += 1
                        pitchers[p_name]['HR'] += 1
                    elif "3루타" in text:
                        batters[b_name]['3B'] += 1
                        pitchers[p_name]['H'] += 1
                    elif "2루타" in text:
                        batters[b_name]['2B'] += 1
                        pitchers[p_name]['H'] += 1
                    elif ("1루타" in text or "안타" in text or "내야안타" in text) and "무안타" not in text and "실책" not in text:
                        batters[b_name]['1B'] += 1
                        pitchers[p_name]['H'] += 1
                    elif "볼넷" in text or "고의4구" in text:
                        batters[b_name]['BB'] += 1
                        pitchers[p_name]['BB'] += 1
                        is_ab = False
                    elif "몸에맞" in text or "사구" in text:
                        batters[b_name]['HBP'] += 1
                        pitchers[p_name]['HBP'] += 1
                        is_ab = False
                    elif "삼진" in text or "낫아웃" in text or "루킹" in text or "헛스윙" in text:
                        batters[b_name]['SO'] += 1
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
                        batters[b_name]['AB'] += 1
                    
    # 타자 지표 가공
    b_result = []
    max_pa = 0
    for name, st in batters.items():
        if st['PA'] > max_pa: max_pa = st['PA']
        if st['PA'] < 10: continue # thresholds 임시 하향 조정 (디버깅용)
        
        woba = (0.69*st['BB'] + 0.72*st['HBP'] + 0.89*st['1B'] + 1.27*st['2B'] + 1.62*st['3B'] + 2.10*st['HR']) / max(1, st['PA'])
        ab_val = max(1, st['AB'])
        slg = (st['1B']*1 + st['2B']*2 + st['3B']*3 + st['HR']*4) / ab_val
        avg = (st['1B'] + st['2B'] + st['3B'] + st['HR']) / ab_val
        iso = slg - avg
        
        b_result.append({
            'Player': name,
            'pcode': st.get('pcode', 'Unknown'),
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
        ip = st['Outs'] / 3.0
        if ip < 3: continue # thresholds 임시 하향 조정 (디버깅용)
        
        fip = (13*st['HR'] + 3*(st['BB']+st['HBP']) - 2*st['SO']) / max(0.1, ip) + 3.20
        k9 = (st['SO'] * 9) / max(0.1, ip)
        bb9 = (st['BB'] * 9) / max(0.1, ip)
        
        name = player_names.get(str(pcode), "Unknown")
        p_result.append({
            'Player': name,
            'pcode': pcode,
            'IP': round(ip, 1),
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
    if not df_pitchers.empty:
        df_pitchers.to_csv(f"kbo_pitcher_saber_{year}.csv", index=False, encoding='utf-8-sig')
    
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
