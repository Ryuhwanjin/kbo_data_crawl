import os
import json
import glob
import math
import pandas as pd
from datetime import datetime
import re

def calculate_plate_z(p):
    y0 = p.get("y0")
    vy0 = p.get("vy0")
    ay = p.get("ay")
    z0 = p.get("z0")
    vz0 = p.get("vz0")
    az = p.get("az")
    
    if None in [y0, vy0, ay, z0, vz0, az]:
        return None
        
    target_y = p.get("crossPlateY", 0.7083) 
    
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
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        return [], [], {}
        
    result_data = raw_data.get("result", {})
    text_relay_data = result_data.get("textRelayData", {})
    if not text_relay_data:
        return [], [], {}
        
    game_id = text_relay_data.get("gameId")
    if not game_id:
        return [], [], {}
        
    is_valid_year = False
    try:
        year_val = int(game_id[:4])
        if 2000 <= year_val <= 2027:
            is_valid_year = True
    except:
        pass
        
    player_map = {}
    for lineup_side in ["homeLineup", "awayLineup"]:
        lineup = text_relay_data.get(lineup_side, {})
        for p in lineup.get("pitcher", []):
            if p.get("pcode"):
                player_map[str(p["pcode"])] = p.get("name")
        for b in lineup.get("batter", []):
            if b.get("pcode"):
                player_map[str(b["pcode"])] = b.get("name")
                
    relays = text_relay_data.get("textRelays", [])
    if not relays:
        return [], [], {}
        
    date_str = game_id[:8]
    try:
        game_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except:
        game_date = "Unknown"
        
    game_pitches = []
    game_outliers = []
    game_pitcher_stats = {}
    
    prev_out = 0
    prev_home_score = 0
    prev_away_score = 0
    
    # KBO JSON 이벤트 순서는 보통 relays가 최신순(앞이 9회, 뒤가 1회)이므로 reversed(relays)로 과거부터 훓습니다.
    for tr in reversed(relays):
        inn = tr.get("inn")
        text_opts = tr.get("textOptions", [])
        pts_opts = tr.get("ptsOptions", [])
        pts_map = {pts["ballcount"]: pts for pts in pts_opts if pts.get("ballcount") is not None}
        
        # 💡 [버그 픽스]: textOptions 내부 또한 최신 투구/결과가 인덱스 0에 있고, 초구가 뒤에 있는 구조입니다!
        # 따라서 시간 정방향(과거->현재)으로 이벤트를 재생(Play-by-play)하려면 reversed(text_opts) 를 써야 합니다!
        for opt in reversed(text_opts):
            current_state = opt.get("currentGameState", {})
            opt_type = opt.get("type")
            
            pitcher_code = str(current_state.get("pitcher")) if current_state.get("pitcher") else None
            pitcher_name = player_map.get(pitcher_code, pitcher_code)
            
            curr_out = int(current_state.get("out", prev_out))
            if curr_out < prev_out: 
                prev_out = 0
                
            curr_home_score = int(current_state.get("homeScore", prev_home_score))
            curr_away_score = int(current_state.get("awayScore", prev_away_score))
            
            if pitcher_name and is_valid_year:
                if pitcher_name not in game_pitcher_stats:
                    game_pitcher_stats[pitcher_name] = {
                        "year": year_val, "IP_outs": 0, "R": 0, "H": 0, "BB": 0, "SO": 0, "PA": 0
                    }
                    
                if curr_out > prev_out:
                    delta_out = curr_out - prev_out
                    game_pitcher_stats[pitcher_name]["IP_outs"] += delta_out
                    
                delta_score = 0
                if curr_home_score > prev_home_score:
                    delta_score += (curr_home_score - prev_home_score)
                if curr_away_score > prev_away_score:
                    delta_score += (curr_away_score - prev_away_score)
                    
                if delta_score > 0:
                    game_pitcher_stats[pitcher_name]["R"] += delta_score
                    
                if opt_type == 13:
                    text_result = opt.get("text", "")
                    game_pitcher_stats[pitcher_name]["PA"] += 1
                    
                    if re.search(r"안타|홈런|2루타|3루타", text_result):
                        game_pitcher_stats[pitcher_name]["H"] += 1
                    elif re.search(r"볼넷|몸에 맞는 볼|고의4구", text_result):
                        game_pitcher_stats[pitcher_name]["BB"] += 1
                    elif re.search(r"삼진", text_result):
                        game_pitcher_stats[pitcher_name]["SO"] += 1
                        
                if opt_type == 1 and opt.get("pitchNum") is not None:
                    pitch_num = opt.get("pitchNum")
                    speed_val = opt.get("speed")
                    
                    batter_code = str(current_state.get("batter")) if current_state.get("batter") else None
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
                        "pitch_type": opt.get("stuff"),
                        "speed_kmh": float(speed_val) if speed_val and str(speed_val).replace('.','',1).isdigit() else None,
                        "pitch_result": opt.get("pitchResult"),
                        "text_comment": opt.get("text"),
                        "stance": pts_data.get("stance") if pts_data else None,
                        "release_x": pts_data.get("x0") if pts_data else None,
                        "release_y": pts_data.get("y0") if pts_data else None,
                        "release_z": pts_data.get("z0") if pts_data else None,
                        "plate_x": pts_data.get("crossPlateX") if pts_data else None,
                        "plate_z": plate_z,
                        "sz_top": pts_data.get("topSz") if pts_data else None,
                        "sz_bottom": pts_data.get("bottomSz") if pts_data else None
                    }
                    if is_valid_year:
                        game_pitches.append(pitch_record)
                    else:
                        pitch_record["raw_game_id_prefix"] = game_id[:4]
                        game_outliers.append(pitch_record)
                        
            prev_out = curr_out
            prev_home_score = curr_home_score
            prev_away_score = curr_away_score
                
    return game_pitches, game_outliers, game_pitcher_stats

def main():
    root_dir = "./kbo_data"
    output_csv = "./kbo_data/kbo_pitch_dataset.csv"
    summary_csv = "./kbo_data/kbo_pitcher_summary.csv"
    
    print("=" * 60)
    print("        KBO 투구 데이터 파이프라인 (자체 스탯 집계 엔진 탑재)")
    print("=" * 60)
    
    search_path = os.path.join(root_dir, "**", "kbo_relay_*.json")
    json_files = glob.glob(search_path, recursive=True)
    
    if not json_files:
        return
        
    all_pitches = []
    global_pitcher_stats = {}
    
    for idx, fpath in enumerate(json_files, 1):
        pitches, outliers, game_stats = process_single_game(fpath)
        if pitches:
            all_pitches.extend(pitches)
            
        for p_name, st in game_stats.items():
            year = st["year"]
            key = f"{p_name}_{year}"
            if key not in global_pitcher_stats:
                global_pitcher_stats[key] = {
                    "player_name": p_name, "year": year, 
                    "IP_outs": 0, "R": 0, "H": 0, "BB": 0, "SO": 0, "PA": 0
                }
            g = global_pitcher_stats[key]
            g["IP_outs"] += st["IP_outs"]
            g["R"] += st["R"]
            g["H"] += st["H"]
            g["BB"] += st["BB"]
            g["SO"] += st["SO"]
            g["PA"] += st["PA"]
            
    print(f"✅ 투구 데이터 파싱 완료 (총 {len(all_pitches)}개)")
    
    if all_pitches:
        df_normal = pd.DataFrame(all_pitches)
        df_normal["year"] = df_normal["date"].astype(str).str[:4].astype(int)
        df_normal.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 투구 데이터셋 저장 완료 -> {output_csv}")
        
    if global_pitcher_stats:
        summary_rows = []
        for key, st in global_pitcher_stats.items():
            ip_outs = st["IP_outs"]
            er = st["R"]
            h = st["H"]
            bb = st["BB"]
            pa = st["PA"]
            
            ip_float = ip_outs / 3.0
            era = (er * 9.0) / ip_float if ip_float > 0 else 0.0
            whip = (bb + h) / ip_float if ip_float > 0 else 0.0
            ab_approx = pa - bb
            avg = h / ab_approx if ab_approx > 0 else 0.0
            
            summary_rows.append({
                "player_name": st["player_name"],
                "year": st["year"],
                "IP_float": round(ip_float, 1),
                "ERA": round(era, 2),
                "WHIP": round(whip, 2),
                "AVG": round(avg, 3),
                "SO": st["SO"],
                "BB": bb,
                "H": h,
                "R": er
            })
            
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 자체 산출 요약 통계 저장 완료 -> {summary_csv}")

if __name__ == "__main__":
    main()
