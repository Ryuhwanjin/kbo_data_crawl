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
    y0 = p.get("y0")
    vy0 = p.get("vy0")
    ay = p.get("ay")
    z0 = p.get("z0")
    vz0 = p.get("vz0")
    az = p.get("az")
    
    if None in [y0, vy0, ay, z0, vz0, az]:
        return None
        
    target_y = p.get("crossPlateY", 0.7083) # 홈플레이트 중심 부근 위치 기본값 (약 0.7피트)
    
    a = 0.5 * ay
    b = vy0
    c = y0 - target_y
    
    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return None
        
    if a != 0:
        t1 = (-b - math.sqrt(discriminant)) / (2 * a)
        t2 = (-b + math.sqrt(discriminant)) / (2 * a)
        t = t1 if 0.1 <= t1 <= 1.0 else (t2 if 0.1 <= t2 <= 1.0 else None)
    else:
        t = -c / b if b != 0 else None
        
    if t is None or t <= 0:
        return None
        
    plate_z = z0 + vz0 * t + 0.5 * az * t**2
    return plate_z

def process_single_game(json_path):
    """경기 JSON 파일을 파싱하여 정상 투구 데이터와 격리된 이상치 데이터를 분리 반환합니다."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"⚠️ 파일 로드 실패: {json_path} ({e})")
        return [], []
        
    result_data = raw_data.get("result", {})
    if not result_data:
        return [], []
        
    text_relay_data = result_data.get("textRelayData", {})
    if not text_relay_data:
        return [], []
        
    game_id = text_relay_data.get("gameId")
    if not game_id:
        return [], []
        
    # 연도 유효성 검사 (이상치 감지용 플래그)
    is_valid_year = False
    try:
        year_val = int(game_id[:4])
        if 2000 <= year_val <= 2027:
            is_valid_year = True
    except Exception:
        pass
        
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
                
    # 2. 문자 중계 리스트 순회
    relays = text_relay_data.get("textRelays", [])
    if not relays:
        return [], []
        
    date_str = game_id[:8]
    try:
        game_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except:
        game_date = "Unknown"
        
    game_pitches = []
    game_outliers = []
    
    for tr in reversed(relays):
        inn = tr.get("inn")
        text_opts = tr.get("textOptions", [])
        pitch_opts = [o for o in text_opts if o.get("type") == 1 and o.get("pitchNum") is not None]
        pts_opts = tr.get("ptsOptions", [])
        
        pts_map = {}
        for pts in pts_opts:
            if pts.get("ballcount") is not None:
                pts_map[pts["ballcount"]] = pts
                
        for p_opt in pitch_opts:
            pitch_num = p_opt["pitchNum"]
            speed_val = p_opt.get("speed")
            
            state = p_opt.get("currentGameState", {})
            pitcher_code = str(state.get("pitcher")) if state.get("pitcher") else None
            batter_code = str(state.get("batter")) if state.get("batter") else None
            
            pitcher_name = player_map.get(pitcher_code, pitcher_code)
            batter_name = player_map.get(batter_code, batter_code)
            
            pts_data = pts_map.get(pitch_num, {})
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
                "release_x": pts_data.get("x0") if pts_data else None,
                "release_y": pts_data.get("y0") if pts_data else None,
                "release_z": pts_data.get("z0") if pts_data else None,
                "plate_x": pts_data.get("crossPlateX") if pts_data else None,
                "plate_z": plate_z,
                "sz_top": pts_data.get("topSz") if pts_data else None,
                "sz_bottom": pts_data.get("bottomSz") if pts_data else None
            }
            
            # 연도가 올바르면 정상 데이터, 올바르지 않으면 이상치 리스트로 라우팅
            if is_valid_year:
                game_pitches.append(pitch_record)
            else:
                pitch_record["raw_game_id_prefix"] = game_id[:4] # 이상치 원인 기록용 추가
                game_outliers.append(pitch_record)
                
    return game_pitches, game_outliers

def main():
    root_dir = "./kbo_data"
    output_csv = "./kbo_data/kbo_pitch_dataset.csv"
    outlier_csv = "./kbo_data/kbo_pitch_outliers.csv"
    
    print("=" * 60)
    print("        KBO PTS 투구 데이터 이중 격리 정제 파이프라인 (ETL)")
    print(f"        스캔 대상 디렉토리: {os.path.abspath(root_dir)}")
    print("=" * 60)
    
    search_path = os.path.join(root_dir, "**", "kbo_relay_*.json")
    json_files = glob.glob(search_path, recursive=True)
    
    print(f"🔍 총 {len(json_files)}개의 경기 JSON 파일을 감지했습니다.")
    if not json_files:
        print("❌ 파싱할 JSON 파일이 없습니다.")
        return
        
    all_pitches = []
    all_outliers = []
    success_games = 0
    
    for idx, fpath in enumerate(json_files, 1):
        filename = os.path.basename(fpath)
        pitches, outliers = process_single_game(fpath)
        if pitches or outliers:
            all_pitches.extend(pitches)
            all_outliers.extend(outliers)
            success_games += 1
            
    print("-" * 60)
    print(f"정리 완료: {success_games}/{len(json_files)} 경기 파싱")
    print(f"  - 정상 투구 레코드 수: {len(all_pitches)}개")
    print(f"  - 이상치 투구 레코드 수: {len(all_outliers)}개")
    print("-" * 60)
    
    # 1. 정상 데이터 저장
    if all_pitches:
        df_normal = pd.DataFrame(all_pitches)
        df_normal["year"] = pd.to_datetime(df_normal["date"], errors="coerce").dt.year
        df_normal.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 정상 데이터셋 저장 완료 -> {output_csv}")
    else:
        print("⚠️ 저장할 정상 데이터가 없습니다.")
        
    # 2. 이상치 데이터 격리 저장
    if all_outliers:
        df_outliers = pd.DataFrame(all_outliers)
        df_outliers.to_csv(outlier_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 이상치 데이터 격리 저장 완료 -> {outlier_csv}")
    else:
        # 이상치가 없는 경우 기존 파일이 있다면 안전하게 제거
        if os.path.exists(outlier_csv):
            os.remove(outlier_csv)
        print("ℹ️ 이상치 데이터가 검출되지 않았습니다.")
        
    print("============================================================")

if __name__ == "__main__":
    main()
