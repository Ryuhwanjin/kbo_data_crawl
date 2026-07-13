# ⚾️ KBO PTS Data Extraction & Analysis Suite

KBO 문자중계와 PTS(Pitch Tracking System) 3D 투구 좌표를 결합하여 데이터 수집(Extract), 이중 격리 정제(Transform/Load), 세이버메트릭스 누적 집계, 스탯캐스트(Statcast) 스타일 시각화 엔진, 그리고 디스코드 봇 및 개인 아이디어 기획 메모장 비서를 아우르는 통합 야구 분석 데이터 파이프라인 시스템입니다.

---

## 🏛️ 프로젝트 폴더 구조 및 아키텍처

프로젝트의 효율적인 유지보수와 구조화를 위해 파이썬 파일들이 기능별 서브디렉토리로 깔끔하게 정리되어 있습니다.

```
/Users/ryuhwanjin/Desktop/Project/인생/
├── bots/                  # 디스코드 및 소셜 봇 관련 핵심 실행 파일
│   ├── kbo_discord_bot.py
│   └── kbo_social_bot.py
├── crawlers/              # 네이버 KBO 크롤러 및 뉴스 스크래퍼
│   ├── kbo_news_scraper.py
│   ├── naver_kbo_crawler.py
│   ├── naver_kbo_pipeline.py
│   └── naver_kbo_summary.py
├── analytics/             # 세이버메트릭스 데이터 분석 및 WAR 연산
│   ├── kbo_sabermetrics.py
│   ├── kbo_war_engine.py
│   └── extract_unique_players.py
├── simulation/            # 경기 시뮬레이터
│   └── kbo_match_simulator.py
├── visualization/         # 대시보드, 차트, 카드 이미지 렌더러
│   ├── kbo_card_generator.py
│   ├── kbo_chart_generator.py
│   ├── kbo_dashboard.py
│   └── naver_kbo_visualizer.py
├── utils/                 # 스케줄 관리자, 유효성 검사기, 아이디어 메모
│   ├── bulk_validator.py
│   ├── daily_kbo_updater.py
│   ├── fast_local_validator.py
│   └── kbo_idea_memo.py
├── kbo_data/              # 수집된 KBO 경기 데이터 (일자별 JSON)
├── kbo_test_data/         # 테스트용 샘플 데이터
├── saber_data/            # 세이버메트릭스 누적 데이터 및 JSON 보정치 캐시
├── logs/                  # 봇 및 스케줄러 실행 로그
├── tests/                 # 단위 테스트 코드
└── ideas.md               # 아이디어 메모장 (마크다운 컴파일 결과물)
```

---

## 🛠️ 1. 데이터 엔지니어링 & ETL 파이프라인

### 1) KBO 데이터 수집기 (`crawlers/naver_kbo_crawler.py`)
* 연도 범위(`--years`) 및 출력 디렉토리(`--out`)를 파라미터로 지정하여, 네이버 스포츠 API-GW로부터 경기 일정 및 릴레이 JSON 데이터를 실시간으로 비동기 수집합니다.
* 경기당 `1.2초 ~ 1.5초` 의 참조 지연(Rate-limiting 우회)을 설정하여 안전하게 백그라운드 태스크로 대량 다운로드를 수행합니다.

### 2) 이중 격리 정제 파이프라인 (`crawlers/naver_kbo_pipeline.py`)
* 다운로드된 경기 JSON 데이터를 순회하며 PTS 3D 릴리스 포인트($x_0, y_0, z_0$), 가속도 파라미터, 홈플레이트 통과 2D 좌표 및 문자중계 텍스트를 결합하여 정형 데이터셋으로 변환합니다.
* **이중 트랙 격리(Outliers Isolation) 적용**: 
  * 경기 `gameId` 의 연도가 타당한 야구 정규시즌 범위(`2000년 ~ 2027년`)를 벗어나는 불량 및 테스트용 데이터(예: `3333`년, `7777`년)가 감지되면 완전히 Drop 시키지 않고 **`saber_data/kbo_pitch_outliers.csv`**에 격리 보존합니다.

### 3) 선수별 시즌 요약 통계 엔진 (`crawlers/naver_kbo_summary.py`)
* 정제된 데이터셋을 읽어와 타자별 시즌 비율 지표(AVG, OBP, SLG, OPS) 및 투수별 비율 지표(ERA, WHIP)를 연산하여 종합 스탯 CSV를 빌드합니다.
* **데이터 무결성 예외 처리**:
  * **야구 수학적 이닝 변환**: 소수점 이닝(예: `"1.1"` 또는 `"0.2"`)을 `정수이닝 + (아웃카운트 / 3.0)` 공식으로 실수형 이닝(`IP_float`)으로 변환하여 정밀한 평균자책점(ERA) 및 WHIP 분모 연산을 보장합니다.
  * **OBP Division Overflow 보정**: `PA = max(PA, AB + BB + HBP)` 수학적 보정식을 적용하여 OBP 오버플로우를 방지합니다.

### 4) 데이터 정합성 대량 교차 검증 엔진 (`utils/bulk_validator.py` & `analytics/extract_unique_players.py`)
* KBO 텍스트 중계 JSON과 네이버 모바일 공식 기록실의 스탯을 1:1로 비교하여 오차율 0%를 보장하는 강력한 자동화 검증 스위트입니다.

---

## 🎨 2. 스탯캐스트 스타일 시각화 엔진 (`visualization/naver_kbo_visualizer.py`)

### 1) 투수용: 구종별 피칭 맵 (`Pitch Heatmap`)
* 가로 분할 서브플롯(Subplots)을 통해 투수가 던진 유효 구종별 투구 밀도를 등고선으로 렌더링합니다.
* 라벨과 축을 숨긴 초미니멀 프레임을 채택하여 시각적 효과를 높였으며 최소 4구 이상 투구한 구종만 표기되도록 예외 처리가 내장되어 있습니다.

### 2) 타자용: 안타 4분할 야구장 `Spray Chart`
* 안타 계열 데이터만 매핑하며 단타(SINGLE), 2루타(DOUBLE), 3루타(TRIPLE), 홈런(HR) 각각을 고유한 색상 및 마커로 다르게 분기 표기합니다.
* 가상의 비행거리 가중치를 이용해 외야 필드 및 펜스 바깥 영역에 사실적으로 안타가 배치되도록 구현했습니다.

---

## 🚀 3. 사용 방법 (CLI Guide)

모든 파이썬 파일들이 서브디렉토리로 정리되었으므로, 실행 시 적절한 폴더 경로를 명시해야 합니다.

### 1) 데이터 수집 및 정제
```bash
# 1. 2017년부터 2025시즌까지 KBO 경기 JSON 데이터를 백그라운드로 수집
python crawlers/naver_kbo_crawler.py --years 2017,2018,2019,2020,2021,2022,2023,2024,2025 --out ./kbo_data --delay 1.2

# 2. 수집된 JSON 파일들을 읽어와 정상 CSV 및 이상치 격리 CSV로 ETL 변환
python crawlers/naver_kbo_pipeline.py

# 3. 선수별 누적 비율 지표 통계 요약 파일 생성
python crawlers/naver_kbo_summary.py
```

### 2) 파싱 데이터 정합성 전수 교차 검증 (Bulk Validation)
```bash
# KBO 전 시즌(2017~2026)의 파싱 및 네이버 모바일 기록실 1:1 대조 자동 검증 루프
for year in {2017..2026}; do echo "=== [$year] ==="; python3 analytics/kbo_sabermetrics.py --year $year; python3 utils/bulk_validator.py --year $year; done
```

### 3) 투수용 Pitch Heatmap 시각화
```bash
# 2024시즌 주현상 투수의 구종별 히트맵 차트 생성
python visualization/naver_kbo_visualizer.py --pitcher 주현상 --year 2024
```
* **결과 이미지 저장 경로**: `kbo_data/{투수명}_{연도}_pitch_chart.png`

### 4) 타자용 Spray Chart 시각화
```bash
# 2017시즌 박건우 타자의 안타 스프레이 차트 생성
python visualization/naver_kbo_visualizer.py --batter 박건우 --year 2017
```
* **결과 이미지 저장 경로**: `kbo_data/{타자명}_{연도}_spray_chart.png`

---

## 🤖 4. 디스코드 봇 및 스케줄러 & 아이디어 메모장 (`bots/kbo_discord_bot.py`)

KBO 뉴스 큐레이션, 실시간 크롤링, 음악 재생 기능과 더불어 **개인용 비공개 아이디어 메모장** 기능이 탑재되어 있습니다.

### 1) 봇 구동 방법
```bash
# 디스코드 봇 백그라운드 기동
python bots/kbo_discord_bot.py
```

### 2) 주요 기능 및 명령어
* **`!setup`** — `KBO 브리핑 센터` 11개 구단별 채널 및 비공개 `💡 아이디어 메모장` 카테고리/채널을 자동 셋업합니다. (`아이디어-메모장` 채널은 본인과 봇에게만 비공개로 개설됩니다.)
* **`!scrape`** — KBO 공식 뉴스, 네이버 속보, 엠엘비파크 글을 실시간 수집하여 24시간 이내 최신 기사만 각 구단/KBO 채널에 자동 라우팅하여 배포합니다. (중복 전송은 로컬 캐시 `saber_data/posted_links.json`를 통해 영구 방지됩니다.)
* **`⏰ 정기 자동 브리핑`** — 봇 실행 시 백그라운드 스케줄러가 매일 **오전 08:30** 및 **오후 18:30**에 무인 브리핑 배포를 자동으로 수행합니다.

### 3) 💡 개인 아이디어 메모장 명령어 (`#아이디어-메모장` 채널 전용)
* **`!add [내용]`** — 새로운 기획 아이디어/글감을 등록합니다.
* **`!list`** / **`!todo`** — 미완료(TODO) 상태인 기획 목록을 확인합니다.
* **`!done [ID]`** — 해당 ID의 기획을 완료(DONE)로 처리합니다. (완료 즉시 루트의 `ideas.md`에 마크다운 리포트로 자동 컴파일 및 갱신이 이루어집니다.)
* **`!memo`** — 메모장 채널 도움말을 출력합니다.

---

## 🚀 5. 신규 기능 실행 가이드 (데일리 업데이트, WAR, 시뮬레이터)

### 1) 데일리 실시간 수집 및 파이프라인 자동 갱신 (`utils/daily_kbo_updater.py`)
```bash
# 최근 3일간의 종료된 경기를 검사하고, 누락된 경기를 다운로드한 뒤 자동으로 파이프라인을 갱신합니다.
python utils/daily_kbo_updater.py --days 3
```

### 2) KBO 맞춤형 WAR(승리 기여도) 엔진 (`analytics/kbo_war_engine.py`)
```bash
# 특정 시즌의 타자/투수 WAR 지표를 연산하여 CSV 파일에 갱신합니다.
python analytics/kbo_war_engine.py --year 2026
```

### 3) 몬테카를로 경기 시뮬레이터 및 승패 예측 (`simulation/kbo_match_simulator.py`)
```bash
# 몬테카를로 시뮬레이션(2,000회)을 가동하여 승률과 득점 분포를 예측합니다.
python simulation/kbo_match_simulator.py --home 삼성 --away KIA --sims 2000
```
