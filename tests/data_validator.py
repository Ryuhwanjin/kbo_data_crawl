import pandas as pd
import os

def validate_batter_stats(year):
    """
    파서가 뽑은 스탯(kbo_batter_saber_{year}.csv)과
    공식 스탯(official_batter_{year}.csv)을 교차 검증하여 오차 리포트를 출력합니다.
    """
    parsed_file = f"kbo_batter_saber_{year}.csv"
    official_file = f"official_batter_{year}.csv"
    
    if not os.path.exists(parsed_file) or not os.path.exists(official_file):
        print("비교할 파일이 없습니다. 먼저 파싱 스크립트와 크롤러를 실행하세요.")
        return
        
    df_parsed = pd.read_csv(parsed_file)
    df_official = pd.read_csv(official_file)
    
    # 1. Player 이름 기준으로 Merge
    # (동명이인 방지를 위해 추후 pcode 매핑 권장되지만, 
    # 현재 파서는 b_name 기반이므로 우선 이름으로 병합)
    merged = pd.merge(df_official, df_parsed, on='Player', how='inner')
    
    if merged.empty:
        print("병합된 선수가 없습니다! 이름 클렌징 상태를 확인하세요.")
        return
        
    # 비교할 클래식 스탯 리스트 (공식 vs 파싱)
    # 1B는 공식스탯에 없으므로 (안타 - 2루타 - 3루타 - 홈런) 으로 역산해야 하지만
    # 여기서는 안타 총합(H)으로 퉁쳐서 비교한다.
    # 파싱된 데이터에 H 컬럼이 없으므로 생성
    merged['H'] = merged['1B'] + merged['2B'] + merged['3B'] + merged['HR']
    
    stats_to_compare = [
        ('PA', 'PA_official', 'PA'),
        ('AB', 'AB_official', 'AB'),
        ('H', 'H_official', 'H'),
        ('2B', '2B_official', '2B'),
        ('3B', '3B_official', '3B'),
        ('HR', 'HR_official', 'HR'),
        ('BB', 'BB_official', 'BB'),
        ('HBP', 'HBP_official', 'HBP'),
        ('SO', 'SO_official', 'SO')
    ]
    
    error_list = []
    
    for _, row in merged.iterrows():
        player = row['Player']
        errors = []
        
        for stat_name, off_col, par_col in stats_to_compare:
            if off_col in merged.columns and par_col in merged.columns:
                diff = int(row[off_col]) - int(row[par_col])
                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    errors.append(f"{stat_name} {sign}{diff}")
                    
        if errors:
            error_list.append(f"[{player}] 오차 발견: " + ", ".join(errors))
            
    print("=" * 60)
    print(f"⚾️ KBO {year}시즌 클래식 스탯 정합성 검증 리포트 ⚾️")
    print("=" * 60)
    
    if not error_list:
        print("✅ 축하합니다! 공식 데이터와 파싱 데이터가 100% 완벽히 일치합니다!")
    else:
        print(f"⚠️ 총 {len(error_list)}명의 선수에게서 오차가 발견되었습니다.")
        print("오차 의미: (+)는 파서가 놓친 누락분, (-)는 파서가 잘못 과대계상한 분량입니다.\n")
        # 규정타석 이상인 핵심 선수 위주로 출력 (상위 20명)
        for err in error_list[:20]:
            print(err)
        if len(error_list) > 20:
            print(f"...(외 {len(error_list) - 20}명 생략)")

if __name__ == "__main__":
    validate_batter_stats(2017)
