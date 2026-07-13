import os
import json
import glob
import pandas as pd

def parse_inning_to_float(inn_str):
    """
    야구 기록의 이닝 문자열(예: '5.1', '0.2', '7.0', '1.3' 등)을 실수형 값으로 변환합니다.
    - '5.1' -> 5 + 1/3 = 5.333
    - '0.2' -> 0 + 2/3 = 0.667
    - '1.3' -> 2.0 (실제 1.3은 야구 기록상 1이닝 3아웃 = 2이닝으로 간주되지만, 예외처리)
    """
    if not inn_str:
        return 0.0
    try:
        inn_str = str(inn_str).strip()
        if "." in inn_str:
            parts = inn_str.split(".")
            base_inn = float(parts[0])
            outs = float(parts[1])
            # 아웃 카운트가 3 이상인 경우 이닝 반올림 처리
            if outs >= 3:
                base_inn += outs // 3
                outs = outs % 3
            return base_inn + (outs / 3.0)
        else:
            return float(inn_str)
    except ValueError:
        return 0.0

def process_lineup_data(json_files):
    """모든 JSON 파일에서 선수별 성적을 추출해 누적합니다."""
    batters_db = {}
    pitchers_db = {}
    
    for idx, fpath in enumerate(json_files, 1):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            continue
            
        result_data = raw_data.get("result", {})
        if not result_data:
            continue
            
        text_relay_data = result_data.get("textRelayData", {})
        if not text_relay_data:
            continue
            
        # 1. 타자 요약 집계
        for side in ["homeLineup", "awayLineup"]:
            lineup = text_relay_data.get(side, {})
            
            # 타자 성적 누적
            for b in lineup.get("batter", []):
                pcode = str(b.get("pcode"))
                if not pcode or not b.get("name"):
                    continue
                    
                if pcode not in batters_db:
                    batters_db[pcode] = {
                        "player_code": pcode,
                        "player_name": b.get("name"),
                        "team": b.get("teamName", lineup.get("teamName", "Unknown")),
                        "G": 0,
                        "PA": 0,
                        "AB": 0,
                        "H": 0,
                        "HR": 0,
                        "BB": 0,
                        "HBP": 0,
                        "SO": 0,
                        "RBI": 0,
                        "RUN": 0
                    }
                
                # 출장 및 스탯 합산 (출장 경기 수 증분)
                batters_db[pcode]["G"] += 1
                batters_db[pcode]["PA"] += b.get("pa") if b.get("pa") is not None else 0
                batters_db[pcode]["AB"] += b.get("ab") if b.get("ab") is not None else 0
                batters_db[pcode]["H"] += b.get("hit") if b.get("hit") is not None else 0
                batters_db[pcode]["HR"] += b.get("hr") if b.get("hr") is not None else 0
                batters_db[pcode]["BB"] += b.get("bb") if b.get("bb") is not None else 0
                batters_db[pcode]["HBP"] += b.get("hbp") if b.get("hbp") is not None else 0
                batters_db[pcode]["SO"] += b.get("so") if b.get("so") is not None else 0
                batters_db[pcode]["RBI"] += b.get("rbi") if b.get("rbi") is not None else 0
                batters_db[pcode]["RUN"] += b.get("run") if b.get("run") is not None else 0
                
            # 2. 투수 요약 집계
            for p in lineup.get("pitcher", []):
                pcode = str(p.get("pcode"))
                if not pcode or not p.get("name"):
                    continue
                    
                if pcode not in pitchers_db:
                    pitchers_db[pcode] = {
                        "player_code": pcode,
                        "player_name": p.get("name"),
                        "team": p.get("teamName", lineup.get("teamName", "Unknown")),
                        "G": 0,
                        "IP_float": 0.0,
                        "H": 0,
                        "HR": 0,
                        "BB": 0,
                        "HBP": 0,
                        "SO": 0,
                        "R": 0,
                        "ER": 0,
                        "pitch_count": 0
                    }
                
                # 투수 이닝 변환 및 적재
                inn_float = parse_inning_to_float(p.get("inn", "0.0"))
                
                pitchers_db[pcode]["G"] += 1
                pitchers_db[pcode]["IP_float"] += inn_float
                pitchers_db[pcode]["H"] += p.get("hit") if p.get("hit") is not None else 0
                pitchers_db[pcode]["HR"] += p.get("hr") if p.get("hr") is not None else 0
                pitchers_db[pcode]["BB"] += p.get("bb") if p.get("bb") is not None else 0
                pitchers_db[pcode]["HBP"] += p.get("hbp") if p.get("hbp") is not None else 0
                pitchers_db[pcode]["SO"] += p.get("kk") if p.get("kk") is not None else 0 # 투수 삼진 키는 kk
                pitchers_db[pcode]["R"] += p.get("run") if p.get("run") is not None else 0
                pitchers_db[pcode]["ER"] += p.get("er") if p.get("er") is not None else 0
                pitchers_db[pcode]["pitch_count"] += p.get("ballCount") if p.get("ballCount") is not None else 0
                
    return list(batters_db.values()), list(pitchers_db.values())

def main():
    root_dir = "./kbo_data"
    output_batter_csv = "./kbo_data/kbo_batter_summary.csv"
    output_pitcher_csv = "./kbo_data/kbo_pitcher_summary.csv"
    
    print("=" * 60)
    print("        KBO 선수별 누적 요약 데이터셋 생성 (ETL)")
    print("=" * 60)
    
    # 1. 파일 검색
    search_path = os.path.join(root_dir, "**", "kbo_relay_*.json")
    json_files = glob.glob(search_path, recursive=True)
    
    print(f"🔍 총 {len(json_files)}개의 경기 JSON 파일을 감지했습니다.")
    if not json_files:
        print("❌ 파싱할 JSON 파일이 없습니다. 수집을 먼저 완료해 주세요.")
        return
        
    # 2. 라인업 데이터 집계
    batters, pitchers = process_lineup_data(json_files)
    
    print(f"📊 집계 완료: 타자 {len(batters)}명, 투수 {len(pitchers)}명 추출")
    print("-" * 60)
    
    # 3. 타자 지표 연산 및 저장
    if batters:
        df_batter = pd.DataFrame(batters)
        
        # 비율 스탯 연산 전 PA 보정 (일부 데이터의 PA 누락 대응)
        df_batter["PA"] = df_batter[["PA", "AB", "BB", "HBP"]].apply(
            lambda r: max(r["PA"], r["AB"] + r["BB"] + r["HBP"]), axis=1
        )
        
        # 비율 스탯 연산
        df_batter["AVG"] = (df_batter["H"] / df_batter["AB"]).round(3)
        df_batter["OBP"] = ((df_batter["H"] + df_batter["BB"] + df_batter["HBP"]) / df_batter["PA"]).round(3)
        
        # 약식 장타율 (2루타/3루타 부재로 1루타=안타-홈런으로 가정해 안전하게 하향 연산)
        # SLG = (단타*1 + 홈런*4) / AB = (H - HR + 4*HR) / AB = (H + 3*HR) / AB
        df_batter["SLG"] = ((df_batter["H"] + 3 * df_batter["HR"]) / df_batter["AB"]).round(3)
        df_batter["OPS"] = (df_batter["OBP"] + df_batter["SLG"]).round(3)
        
        # 0 나누기 및 결측치 예외 처리 (.fillna)
        df_batter.fillna(0.0, inplace=True)
        
        # 정규 정렬
        df_batter.sort_values(by="PA", ascending=False, inplace=True)
        df_batter.to_csv(output_batter_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 타자 요약 데이터 저장 완료: {output_batter_csv}")
        
    # 4. 투수 지표 연산 및 저장
    if pitchers:
        df_pitcher = pd.DataFrame(pitchers)
        
        # 소수점 이닝 가독성을 위한 문자열 포맷 이닝 생성
        # 예: 5.333 -> 5.1이닝 (5이닝 + 1/3이닝)
        def format_inning(ip_float):
            base_inn = int(ip_float)
            rem = ip_float - base_inn
            outs = round(rem * 3)
            return f"{base_inn}.{outs}"
            
        df_pitcher["IP"] = df_pitcher["IP_float"].apply(format_inning)
        
        # 비율 스탯 연산
        df_pitcher["ERA"] = ((df_pitcher["ER"] * 9) / df_pitcher["IP_float"]).round(2)
        df_pitcher["WHIP"] = ((df_pitcher["BB"] + df_pitcher["H"]) / df_pitcher["IP_float"]).round(2)
        
        # 0 나누기 예외 처리 (이닝이 0인 투수 등)
        df_pitcher.replace([float('inf'), float('-inf')], 0.0, inplace=True)
        df_pitcher.fillna(0.0, inplace=True)
        
        # 컬럼 순서 조정
        cols = [
            "player_code", "player_name", "team", "G", "IP", "IP_float", 
            "H", "HR", "BB", "HBP", "SO", "R", "ER", "pitch_count", "ERA", "WHIP"
        ]
        df_pitcher = df_pitcher[cols]
        
        # 정규 정렬
        df_pitcher.sort_values(by="IP_float", ascending=False, inplace=True)
        df_pitcher.to_csv(output_pitcher_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 투수 요약 데이터 저장 완료: {output_pitcher_csv}")
        
    print("=" * 60)
    print("        선수별 요약 Tabular Data 구축 작업이 끝났습니다!")
    print("=" * 60)

if __name__ == "__main__":
    main()
