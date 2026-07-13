import json
import glob
import pandas as pd
import os

def extract_unique_players():
    print("KBO 텍스트 릴레이 JSON 전체 스캔 중...")
    print("목표: 모든 선수의 고유 식별자(pcode) 마스터 테이블 생성")
    
    # 2017년부터 모든 연도 디렉토리 탐색 (혹시 모르니 상위 디렉토리 기준)
    files = glob.glob('kbo_data/**/*.json', recursive=True)
    if not files:
        print("kbo_data 디렉토리에서 JSON 파일을 찾지 못했습니다.")
        return
        
    print(f"총 {len(files)}개의 JSON 파일을 스캔합니다.")
    unique_players = {} # pcode: name
    for idx, f in enumerate(files):
        if (idx + 1) % 100 == 0:
            print(f"🔄 JSON 파싱 진행 중: [{idx + 1}/{len(files)}] ({(idx+1)/len(files)*100:.1f}%)", flush=True)
            
        with open(f, 'r', encoding='utf-8') as fp:
            try:
                data = json.load(fp)
                relays = data.get('result', {}).get('textRelayData', {}).get('textRelays', [])
                
                for opt in relays:
                    for text_opt in opt.get('textOptions', []):
                        if text_opt.get('type') == 8 and text_opt.get('batterRecord'):
                            name = text_opt['batterRecord'].get('name', 'Unknown')
                            # KBO JSON의 경우 currentGameState.batter 에 타자의 pcode가 들어있음
                            pcode = text_opt.get('currentGameState', {}).get('batter', 'Unknown')
                            
                            if pcode != 'Unknown' and name != 'Unknown':
                                unique_players[pcode] = name
            except Exception as e:
                pass
                
    # DataFrame으로 변환 및 저장
    df = pd.DataFrame(list(unique_players.items()), columns=['pcode', 'PlayerName'])
    
    # 정렬 및 저장
    df = df.sort_values(by='PlayerName')
    out_file = 'unique_players.csv'
    df.to_csv(out_file, index=False, encoding='utf-8-sig')
    
    print(f"\n총 {len(unique_players)}명의 유니크 선수(동명이인 포함) 마스터 테이블 생성 완료: {out_file}")

if __name__ == "__main__":
    extract_unique_players()
