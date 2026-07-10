# KBO PTS 야구 데이터 수집기 (KBO PTS Baseball Data Crawler)

네이버 스포츠 경기 상세 릴레이 및 3D PTS(Pitch Tracking System) 투구 추적 데이터를 자동으로 일괄 수집하여 로컬 데이터 레이크를 구축하는 KBO 전용 데이터 수집 툴킷입니다.

---

## 🚀 주요 기능

1. **정규시즌 자동 필터링 수집**: 2017시즌부터 연도별 공식 정규시즌 및 포스트시즌 경기만 완벽하게 걸러내어 수집합니다. (시범경기 자동 배제)
2. **일별 폴더 트리(Option B) 적재**: 수집된 경기를 `kbo_data/{year}/{month}/{day}/` 구조의 일별 폴더 트리로 자동 분류 보관하여 대용량 파일 탐색 효율성을 극대화합니다.
3. **중복 수집 방지**: 데이터 스캔을 통해 이미 로컬에 적재된 경기는 자동으로 스킵하며 네트워크 호출을 최소화합니다.
4. **IP 차단 방지**: 요청 사이 안전 지연 시간(`delay`)을 조절하여 디도스(DDoS) 의심 차단을 사전에 방지합니다.

---

## 🛠️ 설치 및 사용 방법

### 1. 개발 환경 설정
본 프로젝트는 파이썬 가상환경 사용을 권장합니다.

```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 필수 패키지 설치
pip install -r requirements.txt
```

### 2. 크롤러 실행 (Raw Data 수집)

`naver_kbo_crawler.py` 스크립트를 실행하여 정규시즌 데이터를 일괄 다운로드합니다.

```bash
# 2024시즌 전체 KBO 경기 데이터 수집 (기본 1.5초 딜레이)
python naver_kbo_crawler.py --years 2024

# 2017년부터 2024년까지 다개년 데이터를 일괄 수집
python naver_kbo_crawler.py --years 2017,2018,2019,2020,2021,2022,2023,2024 --out ./kbo_data --delay 1.5

# 특정 단일 날짜의 경기만 수집 (예외 수집 모드)
python naver_kbo_crawler.py --start 2024-05-10 --end 2024-05-10
```

---

## 📁 데이터셋 적재 구조

```text
kbo_data/
└── 2024/
    └── 05/
        └── 10/
            ├── kbo_relay_20240510KTOB02024.json
            ├── kbo_relay_20240510LGLT02024.json
            └── ...
```
각 JSON 파일 내부의 `ptsOptions` 필드에 투수의 3차원 릴리스 포인트(`x0, y0, z0`), 초기 속도 및 가속도 벡터(`vx0, ax...`), 스트라이크 존 정보(`topSz, bottomSz`) 및 홈플레이트 통과 2차원 좌표(`crossPlateX, crossPlateY`)가 포함되어 있습니다.
