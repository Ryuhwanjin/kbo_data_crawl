import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime

def generate_premium_lineup_chart(hitters_df, pitcher_name, title="KBO Daily Best Lineup", out_path="sample_lineup.png"):
    """
    야구장 그라운드(다이아몬드) 위에 선수들을 포지션별로 배치하는 프리미엄 디자인 렌더링 엔진.
    """
    # 애플 시스템 한글 폰트 적용 (맥 환경)
    plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams['axes.unicode_minus'] = False
    
    # 딥 그린 베이스 배경
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 10), facecolor='#0B1F13')
    ax.set_facecolor('#0B1F13')
    
    # 외야 잔디 곡선
    outfield = patches.Wedge((0, -20), 100, 45, 135, facecolor='#10311D', edgecolor='none')
    ax.add_patch(outfield)
    
    # 내야 흙 영역 (다이아몬드)
    infield = patches.Polygon([[0, -10], [-25, 15], [0, 40], [25, 15]], closed=True, facecolor='#593B22', edgecolor='#7A5333', lw=3)
    ax.add_patch(infield)
    
    # 잔디 내야 (루 사이 공간)
    grass_infield = patches.Polygon([[0, 0], [-15, 15], [0, 30], [15, 15]], closed=True, facecolor='#164A29', edgecolor='none')
    ax.add_patch(grass_infield)

    # 타이틀 및 헤더
    ax.text(0, 95, title, fontsize=28, fontweight='heavy', color='#F6D365', ha='center')
    ax.text(0, 88, f"{datetime.now().strftime('%Y-%m-%d')} 통합 MVP 라인업", fontsize=14, color='#A8D0E6', ha='center')
    
    # 포지션별 (x, y) 좌표 및 9명 타자 할당
    # 다이아몬드 홈[0,-10], 1루[25,15], 2루[0,40], 3루[-25,15] 기준
    positions = [
        ("C (포수)", (0, -15)),
        ("1B (1루수)", (28, 15)),
        ("2B (2루수)", (12, 32)),
        ("3B (3루수)", (-28, 15)),
        ("SS (유격수)", (-12, 32)),
        ("LF (좌익수)", (-35, 65)),
        ("CF (중견수)", (0, 75)),
        ("RF (우익수)", (35, 65)),
        ("DH (지명타자)", (-35, -15))
    ]
    
    # 선수 카드 그리기 헬퍼 함수
    def draw_player_card(x, y, position, name, stat_text, is_pitcher=False):
        # 카드 배경 (반투명 글래스 느낌)
        color = '#E74C3C' if is_pitcher else '#2980B9'
        box = patches.FancyBboxPatch((x-12, y-4), 24, 8, boxstyle="round,pad=1,rounding_size=2", 
                                     facecolor=color, alpha=0.85, edgecolor='#ECF0F1', lw=1.5)
        ax.add_patch(box)
        
        # 텍스트
        ax.text(x, y+5, position, fontsize=10, fontweight='bold', color='#F1C40F', ha='center', va='center')
        ax.text(x, y, name, fontsize=15, fontweight='heavy', color='white', ha='center', va='center')
        ax.text(x, y-5, stat_text, fontsize=11, color='#ECF0F1', ha='center', va='center')

    # 마운드 (투수 1위) - 정중앙
    draw_player_card(0, 15, "SP (선발투수)", pitcher_name, "FIP: 1.12", is_pitcher=True)
    
    # 타자 9명 배치
    top_9_hitters = hitters_df.head(9) if not hitters_df.empty else pd.DataFrame()
    for i, (_, row) in enumerate(top_9_hitters.iterrows()):
        if i >= len(positions): break
        pos_name, (px, py) = positions[i]
        draw_player_card(px, py, pos_name, row['Player'], f"wOBA {row['wOBA']:.3f}")

    # 축 설정
    ax.set_xlim(-60, 60)
    ax.set_ylim(-30, 105)
    ax.axis('off')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    # Test Data
    data = [
        {'Player': '김도영', 'wOBA': 0.850}, {'Player': '구자욱', 'wOBA': 0.720},
        {'Player': '최정', 'wOBA': 0.650}, {'Player': '로하스', 'wOBA': 0.610},
        {'Player': '박동원', 'wOBA': 0.580}, {'Player': '문보경', 'wOBA': 0.550},
        {'Player': '손아섭', 'wOBA': 0.510}, {'Player': '김혜성', 'wOBA': 0.490},
        {'Player': '홍창기', 'wOBA': 0.450}
    ]
    df = pd.DataFrame(data)
    generate_premium_lineup_chart(df, pitcher_name='류현진', out_path='sample_lineup_premium.png')
    print("Premium Chart Generated.")
