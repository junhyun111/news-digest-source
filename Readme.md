# 뉴스 다이제스트

네이버 뉴스 검색 API로 기사를 수집하고, 규칙·최신성·임베딩 유사도·MMR을 이용해 추천한 뒤 이메일로 발송하는 Python 애플리케이션입니다.

> `python main.py`를 옵션 없이 실행하면 뉴스 수집 후 이메일을 즉시 발송합니다. 최초 확인과 테스트에는 반드시 `--dry-run`을 사용하세요.

## 주요 기능

- 이노뎁, 보안, 업계동향, 정부/공공, 벤처/금융, 생산/임금 기사 수집
- 한국 시간 기준 전날 오전 7시부터 당일 오전 7시까지 기사 선별
- 월요일은 금요일 오전 7시부터 월요일 오전 7시까지 선별
- 규칙 점수와 과거 기사 임베딩을 결합한 추천
- 업계동향을 7개 편집 의도로 분류
- 업계동향 기존 점수 70%와 편집 점수 30% 결합
- AI 중심성, 산업 중요도, 홍보성, 의도 적합도 평가
- URL·제목·임베딩 중복 제거와 MMR 다양성 선택
- 카테고리별 목표 수량과 상한 적용
- 수집과 이메일 발송을 JSON 파일로 분리 실행
- 텍스트 및 반응형 HTML 이메일 생성

## 요구 사항

- Windows 10/11
- Python 3.14 권장
- 네이버 검색 API Client ID와 Client Secret
- SMTP 로그인이 가능한 이메일 계정
- 프로젝트에 포함된 `model/embeddings` 기준 임베딩 파일
- 최초 모델 설치를 위한 인터넷 연결

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 모델은 최초 의미 추천 실행 시 Hugging Face에서 내려받고 이후 사용자 로컬 캐시를 사용합니다.

## 최초 설치

PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
Set-Location C:\path\to\news-digest-source
```

가상환경을 만들고 의존성을 설치합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

환경변수 예시 파일을 복사합니다.

```powershell
Copy-Item .env.sample .env
```

`.env`를 열어 실제 인증 정보와 수신자를 입력합니다.

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
REAL_RECIPIENTS=team@example.com,team2@example.com
TIMEZONE=Asia/Seoul

MIN_SCORE=15
MAX_ARTICLES=35
MMR_LAMBDA=0.70

SEMANTIC_RECOMMENDATION_ENABLED=true
SEMANTIC_EMBEDDING_DIR=model/embeddings
USE_SAMPLE_DATA=false
```

여러 수신자는 쉼표로 구분합니다. 실제 운영 전에는 `TEST_MODE=true`와 본인의 시험용 주소를 사용하세요. 시험 수신자와 실제 수신자가 겹치면 안전을 위해 발송이 중단됩니다.

## 최초 실행 순서

### 1. 외부 API 없이 기본 흐름 확인

`.env`에서 잠시 `USE_SAMPLE_DATA=true`로 설정한 뒤 실행합니다.

```powershell
.\.venv\Scripts\python.exe main.py --dry-run
```

메일은 발송되지 않습니다. 확인 후 실제 네이버 뉴스를 사용하려면 `USE_SAMPLE_DATA=false`로 되돌립니다.

### 2. 실제 뉴스 수집과 추천 확인

```powershell
.\.venv\Scripts\python.exe main.py --dry-run
```

드라이런 하단에는 업계동향 후보의 다음 정보가 출력됩니다.

- 기존 점수, 편집 점수, 최종 점수
- AI 중심성 및 산업 중요도
- 7개 편집 의도 중 분류 결과
- 선정 또는 탈락 이유

상세 실행 로그가 필요하면 `--verbose`를 추가합니다.

```powershell
.\.venv\Scripts\python.exe main.py --dry-run --verbose
```

### 3. 시험 이메일 발송

`.env`의 `TEST_MODE=true`와 `TEST_RECIPIENTS`를 확인한 뒤 실행합니다.

```powershell
.\.venv\Scripts\python.exe main.py
```

이 명령은 뉴스 수집부터 이메일 발송까지 즉시 실행합니다.

### 4. 실제 수신자로 전환

시험 이메일을 확인한 뒤 `.env`를 다음과 같이 변경합니다.

```dotenv
TEST_MODE=false
REAL_RECIPIENTS=team@example.com,team2@example.com
```

## 실행 명령

| 명령 | 동작 | 이메일 발송 |
| --- | --- | --- |
| `python main.py --dry-run` | 수집·추천 결과와 진단 출력 | 안 함 |
| `python main.py --prepare-output prepared-digest.json` | 수집·추천 결과를 JSON으로 저장 | 안 함 |
| `python main.py --send-prepared prepared-digest.json` | 저장된 JSON을 이메일로 발송 | 함 |
| `python main.py` | 수집·추천 후 즉시 이메일 발송 | 함 |

실제 실행에서는 가상환경의 Python 경로를 사용하는 것이 안전합니다.

```powershell
.\.venv\Scripts\python.exe main.py --prepare-output prepared-digest.json
.\.venv\Scripts\python.exe main.py --send-prepared prepared-digest.json
```

`--send-prepared` 동작은 다음과 같습니다.

- 발송 성공: 사용한 JSON 파일 삭제
- 발송 실패: 재시도를 위해 JSON 파일 보존
- JSON 파일이 없거나 손상됨: 이메일을 발송하지 않고 오류 종료

## 추천 시간 범위와 수량

발행 시각은 `Asia/Seoul`을 기준으로 판정합니다.

- 화요일~일요일: 전날 오전 7시 초과부터 당일 오전 7시 이하
- 월요일: 금요일 오전 7시 초과부터 월요일 오전 7시 이하

목표는 품질 조건을 충족하는 후보가 있을 때 우선 확보하려는 수량이며, 상한은 절대 최대 수량입니다.

| 카테고리 | 목표 | 상한 |
| --- | ---: | ---: |
| 보안 관련 기사 | 5 | 10 |
| 업계동향 기사 | 16 | 22 |
| 벤처/금융 기사 | 5 | 9 |

전체 이메일의 기본 상한은 35건입니다.

## 권장 Windows 작업 스케줄러 구성

프로그램을 30분 동안 대기시키지 않고 수집과 발송을 별도 작업으로 등록하는 방식을 권장합니다.

```text
오전 7:05  뉴스 수집·추천 → prepared-digest.json 저장
오전 7:30  prepared-digest.json 이메일 발송 → 성공 시 JSON 삭제
```

오전 7시 5분에 실행해도 기사 판정 종료 시각은 당일 오전 7시로 고정됩니다.

예시 프로젝트 경로가 `C:\Users\사용자\Desktop\news-digest-source`라고 가정합니다. 실제 환경에서는 본인의 절대 경로로 바꾸세요.

### 작업 1: 뉴스 수집 및 JSON 저장

1. 작업 스케줄러를 실행합니다.
2. 오른쪽 메뉴에서 **작업 만들기**를 선택합니다.
3. 이름을 `뉴스 다이제스트 - 수집`로 지정합니다.
4. **트리거**에서 매일 오전 `7:05`를 등록합니다.
5. **동작 → 새로 만들기 → 프로그램 시작**을 선택합니다.
6. 다음 값을 입력합니다.

| 입력란 | 값 |
| --- | --- |
| 프로그램/스크립트 | `C:\Users\사용자\Desktop\news-digest-source\.venv\Scripts\python.exe` |
| 인수 추가 | `main.py --prepare-output prepared-digest.json` |
| 시작 위치 | `C:\Users\사용자\Desktop\news-digest-source` |

### 작업 2: 준비된 JSON 이메일 발송

1. 새 작업을 만들고 이름을 `뉴스 다이제스트 - 발송`으로 지정합니다.
2. **트리거**에서 매일 오전 `7:30`을 등록합니다.
3. **동작 → 새로 만들기 → 프로그램 시작**을 선택합니다.
4. 다음 값을 입력합니다.

| 입력란 | 값 |
| --- | --- |
| 프로그램/스크립트 | `C:\Users\사용자\Desktop\news-digest-source\.venv\Scripts\python.exe` |
| 인수 추가 | `main.py --send-prepared prepared-digest.json` |
| 시작 위치 | `C:\Users\사용자\Desktop\news-digest-source` |

### 두 작업의 권장 설정

- **예약된 시작 시간을 놓친 경우 가능한 한 빨리 작업 실행** 활성화
- **작업이 이미 실행 중이면 새 인스턴스를 시작하지 않음** 선택
- 네트워크 연결이 필요하므로 노트북에서는 전원 및 절전 조건 확인
- 가장 높은 수준의 권한은 일반적으로 필요하지 않음
- 작업 기록을 활성화해 종료 코드와 실패 여부 확인
- `시작 위치`는 반드시 프로젝트 루트로 지정

수집 작업이 실패하면 JSON이 생성되지 않으므로 발송 작업도 오류 종료합니다. 발송이 실패하면 JSON이 남아 있어 같은 명령으로 다시 발송할 수 있습니다. 실패한 JSON이 남은 상태에서 다음 날 수집 작업이 실행되면 같은 파일명으로 덮어쓸 수 있으므로, 작업 스케줄러 기록과 JSON 잔존 여부를 확인하세요.

## 주요 환경 변수

| 변수 | 설명 |
| --- | --- |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 검색 API 인증 정보 |
| `SMTP_HOST`, `SMTP_PORT` | SMTP 서버 주소와 포트 |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP 로그인 정보 |
| `MAIL_SENDER` | 이메일 발신 주소 |
| `TEST_MODE` | `true`이면 시험 수신자 사용 |
| `TEST_RECIPIENTS` | 쉼표로 구분한 시험 수신자 |
| `REAL_RECIPIENTS` | 쉼표로 구분한 실제 수신자 |
| `TIMEZONE` | 기본값 `Asia/Seoul` |
| `MIN_SCORE` | 추천 절대점수 기준. 기본값 `15` |
| `MAX_ARTICLES` | 전체 기사 상한. 기본값 `35` |
| `MMR_LAMBDA` | 관련성과 다양성 균형. 기본값 `0.70` |
| `CATEGORY_QUOTAS` | 카테고리별 상한을 직접 덮어쓸 때 사용 |
| `RECOMMENDATION_WEIGHTS` | 추천 신호별 가중치 |
| `SEMANTIC_RECOMMENDATION_ENABLED` | 의미 추천 활성화 여부 |
| `SEMANTIC_EMBEDDING_DIR` | 기준 임베딩 폴더. 기본 `model/embeddings` |
| `USE_SAMPLE_DATA` | 네이버 API 대신 샘플 응답 사용 |

검색어는 `INNODEP_QUERIES`, `SECURITY_QUERIES`, `INDUSTRY_QUERIES`, `GOVERNMENT_QUERIES`, `VENTURE_QUERIES`, `LABOR_QUERIES` 환경변수로 덮어쓸 수 있습니다.

## 처리 흐름

```text
환경 변수 로드
  → 카테고리별 네이버 뉴스 검색
  → 발행 시각 필터링
  → 제외 규칙과 URL·제목 중복 제거
  → 규칙·최신성·출처·임베딩 점수 계산
  → 업계동향 AI 중심성·산업 중요도·홍보성·7개 의도 계산
  → 업계동향 기존 점수 70% + 편집 점수 30% 결합
  → 카테고리별 목표/상한과 MMR 다양성 선택
  → 카테고리 간 의미 중복 제거
  → JSON 저장 또는 SMTP 이메일 발송
```

## 코드 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 로컬 CLI 진입점 |
| `news_digest/runner.py` | 설정 로드, JSON 준비·삭제, 실행과 발송 흐름 조정 |
| `news_digest/config.py` | `.env`와 OS 환경변수를 `Config`로 변환 |
| `news_digest/settings.py` | 기본 검색어와 실행 설정 |
| `news_digest/naver.py` | 네이버 검색 API 호출과 응답 파싱 |
| `news_digest/pipeline.py` | 카테고리별 수집·추천과 최종 중복 제거 |
| `news_digest/recommendation_rules.py` | 추천 키워드, 제외 조건, 목표와 상한 |
| `news_digest/industry_editorial.py` | 업계동향 7개 의도와 편집 점수 |
| `news_digest/cch_mmr_recommender.py` | 관련도 계산과 MMR 기반 선별 |
| `news_digest/semantic_embeddings.py` | 기준 임베딩과 의미 유사도 계산 |
| `news_digest/filters.py` | 추천 시간 범위와 fallback 선별 |
| `news_digest/emailer.py` | 텍스트·HTML 이메일 생성과 SMTP 발송 |
| `model/group_industry_intents.ipynb` | 기존 업계동향 기사를 7개 의도로 묶는 노트북 |
| `model/embeddings/industry_intents` | 7개 편집 의도 기준 임베딩 |

## 문제 해결

### 모델을 내려받지 못함

최초 실행 시 인터넷 연결과 Hugging Face 접근 여부를 확인합니다. 모델 초기화가 실패하면 의미 추천 없이 규칙 기반 방식으로 fallback하지만 추천 품질이 낮아질 수 있습니다.

### 작업 스케줄러에서는 `.env` 또는 모델을 찾지 못함

두 작업 모두 **시작 위치**를 프로젝트 루트로 지정했는지 확인합니다. `SEMANTIC_EMBEDDING_DIR=model/embeddings`는 시작 위치를 기준으로 해석됩니다.

### 발송 후 JSON이 없어짐

정상 동작입니다. `--send-prepared` 발송 성공 후 중복 발송 방지를 위해 JSON을 삭제합니다. 발송 실패 시에는 삭제하지 않습니다.

### 테스트 모드에서 발송되지 않음

`TEST_RECIPIENTS`가 설정되어 있는지, `TEST_RECIPIENTS`와 `REAL_RECIPIENTS`에 같은 주소가 들어 있지 않은지 확인합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
