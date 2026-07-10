import os
import json
import glob
import math
import pandas as pd
from datetime import datetime

def calculate_plate_z(p):
    """
    등가속도 운동 방정식을 이용해 홈플레이트 통과 시점의 공 높이(plate_z, ft)를 계산합니다.
    """
    # 필수 물리 파라미터 확인
    y0 = p.get("y0")
    vy0 = p.get("vy0")
    ay = p.get("ay")
    z0 = p.get("z0")
    vz0 = p.get("vz0")
    az = p.get("az")
    
    if None in [y0, vy0, ay, z0, vz0, az]:
        return None
        
    target_y = p.get("crossPlateY", 0.7083) # 홈플레이트 중심 부근 위치 기본값 (약 0.7피트)
    
    # 2차 방정식: 0.5 * ay * t^2 + vy0 * t + (y0 - target_y) = 0
    # a * t^2 + b * t + c = 0 구조로 변환
    a = 0.5 * ay
    b = vy0
    c = y0 - target_y
    
    # 판별식 계산
    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return None
        
    # 근의 공식 적용 (t > 0 인 실근 찾기)
    if a != 0:
        t1 = (-b - math.sqrt(discriminant)) / (2 * a)
        t2 = (-b + math.sqrt(discriminant)) / (2 * a)
        # 물리적으로 투구 시간이 양수이며 합리적인 범위(0.1 ~ 1.0초)에 드는 근 선택
        t = t1 if 0.1 <= t1 <= 1.0 else (t2 if 0.1 <= t2 <= 1.0 else None)
    else:
        # 가속도가 0인 경우: 등속 운동 t = -c / b
        t = -c / b if b != 0 else None
        
    if t is None or t <= 0:
        return None
        
    # 높이 z(t) 계산: z0 + vz0 * t + 0.5 * az * t^2
    plate_z = z0 + vz0 * t + 0.5 * az * t**2
    return plate_z

def process_single_game(json_path):
    """경기 JSON 파일을 파싱하여 투구 단위(Pitch-by-Pitch) 데이터 리스트를 반환합니다."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"⚠️ 파일 로드 실패: {json_path} ({e})")
        return []
        
    result_data = raw_data.get("result", {})
    if not result_data:
        return []
        
    text_relay_data = result_data.get("textRelayData", {})
    if not text_relay_data:
        return []
        
    game_id = text_relay_data.get("gameId")
    if not game_id or len(game_id) < 4:
        return []
        
    # 연도 유효성 검사 (3333, 7777 등 이상치 차단)
    try:
        year_val = int(game_id[:4])
        if not (2000 <= year_val <= 2027):
            return []
    except Exception:
        return []
    
    # 1. 라인업 기반 pcode -> 선수 이름 매핑 딕셔너리 빌드
    player_map = {}
    for lineup_side in ["homeLineup", "awayLineup"]:
        lineup = text_relay_data.get(lineup_side, {})
        for p in lineup.get("pitcher", []):
            if p.get("pcode"):
                player_map[str(p["pcode"])] = p.get("name")
        for b in lineup.get("batter", []):
            if b.get("pcode"):
                player_map[str(b["pcode"])] = b.get("name")
                
    # 2. 문자 중계 리스트 순회 (시간 순서대로 정렬하기 위해 역순 탐색)
    relays = text_relay_data.get("textRelays", [])
    if not relays:
        return []
        
    # JSON 파일 명의 연도를 백업 날짜로 추출
    date_str = game_id[:8] if game_id else "Unknown"
    try:
        game_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except:
        game_date = "Unknown"
        
    game_pitches = []
    
    # relays 배열은 최신 이닝이 0번이므로 역순(경기 시작 시점)으로 순회
    for tr in reversed(relays):
        inn = tr.get("inn")
        
        # 문자중계의 개별 투구 리스트 (type 1 이 투구 레코드)
        text_opts = tr.get("textOptions", [])
        pitch_opts = [o for o in text_opts if o.get("type") == 1 and o.get("pitchNum") is not None]
        
        # PTS 3D 물리 데이터 리스트
        pts_opts = tr.get("ptsOptions", [])
        
        # ptsOptions를 ballcount 기준으로 매핑하기 위한 사전 구축
        pts_map = {}
        for pts in pts_opts:
            if pts.get("ballcount") is not None:
                pts_map[pts["ballcount"]] = pts
                
        # 각 투구 단위로 데이터 병합 및 정형화
        for p_opt in pitch_opts:
            pitch_num = p_opt["pitchNum"]
            speed_val = p_opt.get("speed")
            
            # 투수/타자 pcode를 currentGameState에서 직접 가져옵니다.
            state = p_opt.get("currentGameState", {})
            pitcher_code = str(state.get("pitcher")) if state.get("pitcher") else None
            batter_code = str(state.get("batter")) if state.get("batter") else None
            
            pitcher_name = player_map.get(pitcher_code, pitcher_code)
            batter_name = player_map.get(batter_code, batter_code)
            
            # PTS 데이터 매치 확인
            pts_data = pts_map.get(pitch_num, {})
            
            # 플레이트 통과 높이 계산
            plate_z = calculate_plate_z(pts_data) if pts_data else None
            
            pitch_record = {
                "game_id": game_id,
                "date": game_date,
                "inning": inn,
                "pitcher_name": pitcher_name,
                "pitcher_code": pitcher_code,
                "batter_name": batter_name,
                "batter_code": batter_code,
                "pitch_num": pitch_num,
                "pitch_type": p_opt.get("stuff"),
                "speed_kmh": float(speed_val) if speed_val and str(speed_val).replace('.','',1).isdigit() else None,
                "pitch_result": p_opt.get("pitchResult"),
                "text_comment": p_opt.get("text"),
                "stance": pts_data.get("stance") if pts_data else None,
                # 3D 릴리스 포인트
                "release_x": pts_data.get("x0") if pts_data else None,
                "release_y": pts_data.get("y0") if pts_data else None,
                "release_z": pts_data.get("z0") if pts_data else None,
                # 홈플레이트 통과 위치
                "plate_x": pts_data.get("crossPlateX") if pts_data else None,
                "plate_z": plate_z,
                "sz_top": pts_data.get("topSz") if pts_data else None,
                "sz_bottom": pts_data.get("bottomSz") if pts_data else None
            }
            game_pitches.append(pitch_record)
            
    return game_pitches

def main():
    root_dir = "./kbo_data"
    output_csv = "./kbo_data/kbo_pitch_dataset.csv"
    
    print("=" * 60)
    print("        KBO PTS 투구 데이터 정제 파이프라인 (ETL)")
    print(f"        스캔 대상 디렉토리: {os.path.abspath(root_dir)}")
    print("=" * 60)
    
    # 1. kbo_data 하위의 모든 json 파일 재귀 검색 (Option B 폴더 트리 지원)
    search_path = os.path.join(root_dir, "**", "kbo_relay_*.json")
    json_files = glob.glob(search_path, recursive=True)
    
    print(f"🔍 총 {len(json_files)}개의 경기 JSON 파일을 감지했습니다.")
    if not json_files:
        print("❌ 파싱할 JSON 파일이 없습니다. 수집을 먼저 완료해 주세요.")
        return
        
    # 2. 모든 경기 데이터를 순회하며 가공
    all_pitches = []
    success_games = 0
    
    for idx, fpath in enumerate(json_files, 1):
        filename = os.path.basename(fpath)
        print(f"[{idx}/{len(json_files)}] {filename} 파싱 중...")
        pitches = process_single_game(fpath)
        if pitches:
            all_pitches.extend(pitches)
            success_games += 1
            
    print("-" * 60)
    print(f"정리 완료: {success_games}/{len(json_files)} 경기 성공")
    print(f"추출된 총 투구 수: {len(all_pitches)}개")
    print("-" * 60)
    
    if not all_pitches:
        print("❌ 추출된 투구 레코드가 없습니다. JSON 구조를 확인하세요.")
        return
        
    # 3. 데이터프레임 변환 및 적재 (CSV 저장)
    df = pd.DataFrame(all_pitches)
    
    # 열 순서 깔끔하게 정렬
    columns_order = [
        "game_id", "date", "inning", "pitcher_name", "batter_name", 
        "pitch_num", "pitch_type", "speed_kmh", "pitch_result", 
        "stance", "release_x", "release_y", "release_z", 
        "plate_x", "plate_z", "sz_top", "sz_bottom", "text_comment"
    ]
    # 존재하는 열만 순서 적용
    available_cols = [col for col in columns_order if col in df.columns]
    df = df[available_cols]
    
    # CSV 저장
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"✅ 정제 데이터셋 저장 완료! 경로: {os.path.abspath(output_csv)}")
    print(f"   (테이블 형태: {df.shape[0]}행 x {df.shape[1]}열)")
    print("=" * 60)

if __name__ == "__main__":
    main()
