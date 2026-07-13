import os
import argparse
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

def get_team_color(team_name):
    """KBO 주요 구단별 상징 테마 컬러 (RGB) 반환"""
    colors = {
        'KIA': (199, 9, 48),      # KIA Tigers Red
        '삼성': (0, 98, 178),      # Samsung Lions Blue
        'LG': (195, 0, 47),        # LG Twins Burgundy
        '두산': (19, 36, 60),       # Doosan Bears Navy
        'SSG': (206, 14, 45),      # SSG Landers Red
        '롯데': (4, 30, 66),        # Lotte Giants Navy
        '한화': (255, 102, 0),     # Hanwha Eagles Orange
        'KT': (0, 0, 0),           # KT Wiz Black
        '키움': (134, 0, 41),      # Kioum Heroes Burgundy
        'NC': (0, 44, 95)          # NC Dinos Navy/Gold
    }
    return colors.get(team_name, (71, 85, 105)) # 기본 슬레이트 그레이

def draw_fallback_background(width, height):
    """배경 템플릿이 없을 때 자동으로 생성할 고품격 ESPN 다크 그라데이션 배경"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 딥 네이비 대각선 그라데이션
    for y in range(height):
        r = int(7 + (21 - 7) * (y / height))
        g = int(10 + (31 - 10) * (y / height))
        b = int(19 + (50 - 19) * (y / height))
        draw.line([0, y, width, y], fill=(r, g, b, 255))
        
    # 은은한 사선 격자 패턴
    for i in range(0, width + height, 80):
        draw.line([i, 0, i - height, height], fill=(255, 255, 255, 6), width=2)
        
    # 중앙 VS 기입
    font_vs_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    try:
        font_vs = ImageFont.truetype(font_vs_path, 80)
    except:
        font_vs = ImageFont.load_default()
    draw.text((width//2, 480), "VS", fill=(100, 116, 139, 100), font=font_vs, anchor="mm")
    
    return image

def generate_matchup_card(home_team, away_team, year=2026, home_win_pct=50.0, away_win_pct=50.0, output_path=None):
    """
    KBO 경기 매치업 선발투수 정보 및 시뮬레이션 승리 확률을
    배경 템플릿 이미지 위에 동적으로 오버레이하여 카드뉴스 생성
    """
    width, height = 1080, 1080
    template_dir = "resources"
    template_path = os.path.join(template_dir, "matchup_template.png")
    
    # 1. 템플릿 로드 또는 폴백 배경 생성
    if os.path.exists(template_path):
        print(f"🎨 [Card Generator] 커스텀 배경 템플릿 로드 성공: {template_path}")
        image = Image.open(template_path).convert("RGBA")
    else:
        print(f"⚠️ [Card Generator] 템플릿 파일이 없어 기본 다크 테마 폴백 배경을 생성합니다.")
        os.makedirs(template_dir, exist_ok=True)
        image = draw_fallback_background(width, height)
        
    draw = ImageDraw.Draw(image)
    
    # 2. 폰트 세팅 (Mac OS 기본 탑재 폰트 로드)
    font_bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    font_kr_path = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    if not os.path.exists(font_bold_path):
        font_bold_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    if not os.path.exists(font_kr_path):
        font_kr_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
        
    try:
        font_title = ImageFont.truetype(font_bold_path, 46)
        font_team = ImageFont.truetype(font_kr_path, 34)
        font_name = ImageFont.truetype(font_kr_path, 54)
        font_stat_val = ImageFont.truetype(font_bold_path, 36)
        font_stat_lbl = ImageFont.truetype(font_kr_path, 26)
        font_pct = ImageFont.truetype(font_bold_path, 52)
        font_sub = ImageFont.truetype(font_kr_path, 24)
    except:
        font_title = font_team = font_name = font_stat_val = font_stat_lbl = font_pct = font_sub = ImageFont.load_default()

    # 3. 로컬 2026시즌 투수 데이터셋에서 선발투수 1순위 정보 조회
    pitcher_csv = f"saber_data/kbo_pitcher_saber_{year}.csv"
    home_pitcher = {"name": "선발미정", "fip": 4.50, "war": 0.0, "so_9": 0.0, "bb_9": 0.0}
    away_pitcher = {"name": "선발미정", "fip": 4.50, "war": 0.0, "so_9": 0.0, "bb_9": 0.0}
    
    if os.path.exists(pitcher_csv):
        df_pit = pd.read_csv(pitcher_csv)
        # 해당 구단의 투수 중 이닝(IP)이 가장 많은 투수를 1선발로 간주
        df_home = df_pit[df_pit['Team'] == home_team].sort_values(by='IP', ascending=False)
        df_away = df_pit[df_pit['Team'] == away_team].sort_values(by='IP', ascending=False)
        
        if not df_home.empty:
            p_row = df_home.iloc[0]
            home_pitcher = {
                "name": p_row['Player'],
                "fip": p_row['FIP'],
                "war": p_row['WAR'],
                "so_9": (p_row['SO'] * 9) / (p_row['Outs']/3) if p_row['Outs'] > 0 else 0,
                "bb_9": (p_row['BB'] * 9) / (p_row['Outs']/3) if p_row['Outs'] > 0 else 0
            }
        if not df_away.empty:
            p_row = df_away.iloc[0]
            away_pitcher = {
                "name": p_row['Player'],
                "fip": p_row['FIP'],
                "war": p_row['WAR'],
                "so_9": (p_row['SO'] * 9) / (p_row['Outs']/3) if p_row['Outs'] > 0 else 0,
                "bb_9": (p_row['BB'] * 9) / (p_row['Outs']/3) if p_row['Outs'] > 0 else 0
            }

    # 4. 좌/우 선발 투수 영역 그리기 (템플릿이 없을 때만 가이드 라운드 카드 렌더링)
    if not os.path.exists(template_path):
        draw.rounded_rectangle([80, 220, 480, 780], radius=24, fill=(15, 23, 42, 180), outline=(get_team_color(away_team) + (120,)), width=2)
        draw.rounded_rectangle([600, 220, 1000, 780], radius=24, fill=(15, 23, 42, 180), outline=(get_team_color(home_team) + (120,)), width=2)
        draw.text((width//2, 90), f"{year} KBO MATCHUP PREVIEW", fill=(241, 245, 249), font=font_title, anchor="mm")
        draw.text((width//2, 145), f"MONTE CARLO GAME SIMULATION REPORT", fill=(100, 116, 139), font=font_sub, anchor="mm")

    # 5. 투수 카드 정보 작성
    # 원정 (좌측)
    draw.text((280, 275), f"{away_team} TIGERS" if away_team=='KIA' else f"{away_team} LIONS" if away_team=='삼성' else f"{away_team} HEROES" if away_team=='키움' else f"{away_team}", fill=get_team_color(away_team), font=font_team, anchor="mm")
    draw.text((280, 345), away_pitcher['name'], fill=(255, 255, 255), font=font_name, anchor="mm")
    draw.line([160, 395, 400, 395], fill=(71, 85, 105, 100), width=1)
    
    stats_l = [
        ("시즌 FIP", f"{away_pitcher['fip']:.2f}"),
        ("투수 WAR", f"{away_pitcher['war']:.2f}"),
        ("탈삼진/9", f"{away_pitcher['so_9']:.2f}"),
        ("볼넷/9", f"{away_pitcher['bb_9']:.2f}")
    ]
    y_pos = 430
    for i, (lbl, val) in enumerate(stats_l):
        draw.text((120, y_pos + i*75), lbl, fill=(148, 163, 184), font=font_stat_lbl, anchor="lm")
        draw.text((440, y_pos + i*75), val, fill=(255, 255, 255), font=font_stat_val, anchor="rm")
        if not os.path.exists(template_path):
            bar_len = int(120 + 200 * (float(val)/10.0 if "FIP" not in lbl else (6.0 - float(val))/6.0))
            bar_len = max(120, min(320, bar_len))
            draw.rounded_rectangle([120, y_pos + i*75 + 28, bar_len, y_pos + i*75 + 32], radius=2, fill=get_team_color(away_team) + (200,))

    # 홈 (우측)
    draw.text((800, 275), f"{home_team} LIONS" if home_team=='삼성' else f"{home_team} TIGERS" if home_team=='KIA' else f"{home_team}", fill=get_team_color(home_team), font=font_team, anchor="mm")
    draw.text((800, 345), home_pitcher['name'], fill=(255, 255, 255), font=font_name, anchor="mm")
    draw.line([680, 395, 920, 395], fill=(71, 85, 105, 100), width=1)
    
    stats_r = [
        ("시즌 FIP", f"{home_pitcher['fip']:.2f}"),
        ("투수 WAR", f"{home_pitcher['war']:.2f}"),
        ("탈삼진/9", f"{home_pitcher['so_9']:.2f}"),
        ("볼넷/9", f"{home_pitcher['bb_9']:.2f}")
    ]
    for i, (lbl, val) in enumerate(stats_r):
        draw.text((640, y_pos + i*75), lbl, fill=(148, 163, 184), font=font_stat_lbl, anchor="lm")
        draw.text((960, y_pos + i*75), val, fill=(255, 255, 255), font=font_stat_val, anchor="rm")
        if not os.path.exists(template_path):
            bar_len = int(640 + 200 * (float(val)/10.0 if "FIP" not in lbl else (6.0 - float(val))/6.0))
            bar_len = max(640, min(840, bar_len))
            draw.rounded_rectangle([640, y_pos + i*75 + 28, bar_len, y_pos + i*75 + 32], radius=2, fill=get_team_color(home_team) + (200,))

    # 6. 하단 승리 확률 게이지 및 텍스트 렌더링
    if not os.path.exists(template_path):
        draw.rounded_rectangle([80, 830, 1000, 1020], radius=24, fill=(15, 23, 42, 120), outline=(51, 65, 85, 150), width=1)
        draw.text((width//2, 875), "EXPECTED WIN PROBABILITY (예상 승리 확률)", fill=(148, 163, 184), font=font_sub, anchor="mm")
    
    # 게이지 바 렌더링
    bx1, by1, bx2, by2 = 140, 915, 940, 935
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill=(30, 41, 59))
    
    # 원정팀(좌측) 승률 비율만큼 색상 바 칠하기
    split_x = bx1 + int((bx2 - bx1) * (away_win_pct / 100.0))
    draw.rounded_rectangle([bx1, by1, split_x, by2], radius=10, fill=get_team_color(away_team))
    draw.rounded_rectangle([split_x, by1, bx2, by2], radius=10, fill=get_team_color(home_team))
    draw.line([split_x, by1 - 5, split_x, by2 + 5], fill=(255, 255, 255, 255), width=2)
    
    # 텍스트 레이블 기입
    draw.text((bx1, 985), f"{away_team} {away_win_pct:.1f}%", fill=get_team_color(away_team) if get_team_color(away_team)!=(0,0,0) else (255,255,255), font=font_pct, anchor="lm")
    draw.text((bx2, 985), f"{home_team} {home_win_pct:.1f}%", fill=get_team_color(home_team) if get_team_color(home_team)!=(0,0,0) else (255,255,255), font=font_pct, anchor="rm")

    # 7. 최종 이미지 저장
    if not output_path:
        output_path = f"saber_data/kbo_match_card_{away_team}_{home_team}.png"
        
    image.save(output_path, "PNG")
    print(f"📊 [Card Generator] 카드뉴스 빌드 완료 ➡️ {output_path}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=str, required=True, help="홈 팀명 (예: 삼성)")
    parser.add_argument("--away", type=str, required=True, help="원정 팀명 (예: KIA)")
    parser.add_argument("--year", type=int, default=2026, help="스탯 적용 시즌 연도")
    parser.add_argument("--home_pct", type=float, default=50.0, help="홈팀 승리 확률")
    parser.add_argument("--away_pct", type=float, default=50.0, help="원정팀 승리 확률")
    parser.add_argument("--output", type=str, default=None, help="출력 이미지 파일 경로")
    
    args = parser.parse_args()
    generate_matchup_card(
        home_team=args.home,
        away_team=args.away,
        year=args.year,
        home_win_pct=args.home_pct,
        away_win_pct=args.away_pct,
        output_path=args.output
    )
