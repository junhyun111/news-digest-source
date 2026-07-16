# 뉴스 다이제스트

네이버 뉴스 검색 API에서 카테고리별 기사를 수집하고, 규칙·최신성·의미 유사도와 중복도를 기준으로 선별해 이메일로 발송하는 로컬 Python 애플리케이션입니다.

## 주요 기능

- 이노뎁, 보안, 업계 동향, 정부/공공, 벤처/금융, 생산/임금 기사 수집
- 한국 시간 기준 발행 구간 필터링
- 규칙 점수와 기준 임베딩을 결합한 추천
- 업계동향을 7개 편집 의도로 분류하고 기존 점수 70%·편집 점수 30%로 결합
- URL·제목·의미 유사도 기반 중복 제거
- 카테고리별 목표 수량과 상한 적용
- 텍스트 및 반응형 HTML 이메일 생성
- Windows 작업 스케줄러를 이용한 자동 실행

## 요구 사항

- Python 3.14 권장
- 네이버 검색 API Client ID와 Client Secret
- 이메일 발송용 SMTP 계정
- 의미 추천용 `model/embeddings` 데이터

`sentence-transformers` 모델은 최초 실행 시 Hugging Face에서 내려받고 이후 로컬 캐시를 사용합니다.

## 설치

Windows PowerShell 기준:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.sample .env
```

`.env`에 실제 인증 정보와 수신자를 입력합니다. `.env`는 Git에서 제외됩니다.

```dotenv
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret

SMTP_HOST=smtp.naver.com
SMTP_PORT=587
SMTP_USERNAME=sender@example.com
SMTP_PASSWORD=your_app_password
MAIL_SENDER=sender@example.com

TEST_MODE=true
TEST_RECIPIENTS=developer@example.com
REAL_RECIPIENTS=team@example.com
TIMEZONE=Asia/Seoul
```

실제 발송 전에 `TEST_MODE=true`로 시험 수신자에게 먼저 확인하세요. 여러 수신자는 쉼표로 구분합니다.

## 실행

메일을 보내지 않고 현재 추천 결과를 출력합니다.

```powershell
python main.py --dry-run
```

드라이런 하단에는 업계동향 후보의 AI 중심성, 산업 중요도, 편집 의도,
기존/편집/최종 점수와 탈락 이유가 함께 출력됩니다.

상세 로그를 함께 출력합니다.

```powershell
python main.py --dry-run --verbose
```

수집 결과를 JSON으로 준비하거나 준비된 JSON을 발송할 수도 있습니다.

```powershell
python main.py --prepare-output prepared-digest.json
python main.py --send-prepared prepared-digest.json
```

수집부터 실제 메일 발송까지 실행합니다.

```powershell
python main.py
```

네이버 인증 정보 없이 실행 흐름만 확인하려면 `.env`에서 `USE_SAMPLE_DATA=true`를 설정하고 `--dry-run`을 사용합니다.

## 추천 범위와 수량

발행 시각은 `Asia/Seoul` 기준으로 다음 범위를 사용합니다.

- 일반일: 전날 오전 7시 초과부터 당일 오전 7시 이하
- 월요일: 금요일 오전 7시 초과부터 월요일 오전 7시 이하

주요 카테고리 정책은 다음과 같습니다. 목표는 품질 조건을 충족하는 후보가 있을 때 보충할 기준이며, 고품질 후보가 많으면 상한까지 선정될 수 있습니다.

| 카테고리 | 목표 | 상한 |
| --- | ---: | ---: |
| 보안 관련 기사 | 5 | 10 |
| 업계 동향 기사 | 16 | 22 |
| 벤처/금융 기사 | 5 | 9 |

전체 발송 상한은 기본 35건입니다.

## 주요 환경 변수

| 변수 | 설명 |
| --- | --- |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 검색 API 인증 정보 |
| `SMTP_HOST`, `SMTP_PORT` | SMTP 서버와 포트 |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP 로그인 정보 |
| `MAIL_SENDER` | 발신 주소 |
| `TEST_MODE` | `true`이면 시험 수신자 사용 |
| `TEST_RECIPIENTS`, `REAL_RECIPIENTS` | 쉼표로 구분한 수신자 |
| `TIMEZONE` | 기본 `Asia/Seoul` |
| `MIN_SCORE` | 추천 절대점수 기준. 기본 `15` |
| `MAX_ARTICLES` | 전체 기사 상한. 기본 `35` |
| `MMR_LAMBDA` | 관련성과 다양성의 균형. 기본 `0.70` |
| `CATEGORY_QUOTAS` | 카테고리 상한을 직접 덮어쓸 때 사용 |
| `RECOMMENDATION_WEIGHTS` | 추천 신호별 가중치 |
| `SEMANTIC_RECOMMENDATION_ENABLED` | 의미 추천 사용 여부 |
| `SEMANTIC_EMBEDDING_DIR` | 기준 임베딩 폴더 |
| `USE_SAMPLE_DATA` | 실제 API 대신 샘플 응답 사용 |

카테고리별 검색어는 `INNODEP_QUERIES`, `SECURITY_QUERIES`, `INDUSTRY_QUERIES`, `GOVERNMENT_QUERIES`, `VENTURE_QUERIES`, `LABOR_QUERIES`로 덮어쓸 수 있습니다.

## Windows 작업 스케줄러

매일 오전 7시 이후 실행되도록 작업을 등록합니다. 예시는 오전 7시 28분입니다.

1. 작업 스케줄러에서 **작업 만들기**를 선택합니다.
2. 매일 오전 `7:28` 트리거를 만듭니다.
3. 동작을 **프로그램 시작**으로 지정합니다.
4. 다음 값을 입력합니다.

| 입력란 | 값 |
| --- | --- |
| 프로그램 | `C:\path\to\news-digest-source\.venv\Scripts\python.exe` |
| 인수 | `main.py` |
| 시작 위치 | `C:\path\to\news-digest-source` |

`시작 위치`가 없으면 `.env`와 모델 경로를 찾지 못할 수 있습니다. 예약 시간을 놓친 경우 가능한 대로 실행하고, 기존 인스턴스가 실행 중이면 새 인스턴스를 시작하지 않도록 설정하는 것을 권장합니다.

## 처리 흐름

```text
환경 변수 로드
  → 카테고리별 네이버 뉴스 검색
  → 발행 시각 필터링
  → 제외 규칙과 중복 제거
  → 규칙·최신성·출처·의미 점수 계산
  → 업계동향 AI 중심성·산업 중요도·홍보성·7개 의도 점수 계산
  → 업계동향 기존 점수 70% + 편집 점수 30% 결합
  → 카테고리별 목표/상한과 MMR 적용
  → 카테고리 간 중복 제거
  → 이메일 렌더링 및 SMTP 발송
```

## 코드 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 로컬 CLI 진입점 |
| `news_digest/runner.py` | 설정 로드, 수집, 저장, 렌더링, 발송 흐름 조정 |
| `news_digest/config.py` | `.env`와 OS 환경 변수를 `Config`로 변환 |
| `news_digest/settings.py` | 기본 검색어와 실행 설정 |
| `news_digest/naver.py` | 네이버 API 호출과 응답 파싱 |
| `news_digest/pipeline.py` | 카테고리별 수집·추천과 최종 중복 제거 |
| `news_digest/recommendation_rules.py` | 추천 키워드, 제외 조건, 목표와 상한 |
| `news_digest/industry_editorial.py` | 업계동향 7개 의도, 중심성·중요도·홍보성 편집 점수 |
| `news_digest/cch_mmr_recommender.py` | 점수 계산과 MMR 기반 선별 |
| `news_digest/semantic_embeddings.py` | 기준 임베딩과 의미 유사도 계산 |
| `news_digest/filters.py` | 발행 구간과 fallback 선별 |
| `news_digest/emailer.py` | 텍스트/HTML 이메일 생성과 SMTP 발송 |

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
