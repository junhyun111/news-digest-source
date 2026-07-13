# 뉴스 다이제스트

네이버 뉴스 검색 API에서 카테고리별 기사를 수집하고, 관련도와 중복도를 기준으로 선별한 뒤 이메일로 발송하는 Python 애플리케이션입니다. AWS Lambda와 Amazon EventBridge Scheduler를 연결하면 매일 정해진 시각에 자동으로 뉴스 다이제스트를 받을 수 있습니다.

## 주요 기능

- 이노뎁, 보안, 업계 동향, 정부/공공, 벤처/금융, 생산/임금 카테고리별 뉴스 수집
- 기사 최신성, 핵심 키워드, 출처, 엔티티 등을 반영한 관련도 계산
- MMR(Maximal Marginal Relevance)을 이용한 유사 기사 억제와 URL·제목 중복 제거
- 카테고리별 기사 수 제한 및 전체 최대 기사 수 설정
- 텍스트와 HTML 형식의 이메일 발송
- AWS Lambda 정기 실행 및 로컬 미리보기 지원

## 사용자 사용 방법: AWS에서 자동 발송하기

아래 절차는 처음 AWS를 사용하는 경우를 기준으로 설명합니다. AWS 리전은 예시로 서울 리전(`ap-northeast-2`)을 사용합니다.

### 1. 사전 준비

다음 계정과 정보가 필요합니다.

1. **AWS 계정**: [AWS 계정 생성 페이지](https://aws.amazon.com/ko/)에서 계정을 만듭니다.
2. **네이버 검색 API 애플리케이션**: 네이버 개발자 센터 > Application > 애플리케이션 등록 > 애플리케이션 이름 지정(임의) > 사용 API **검색** 선택 > 비로그인 오픈 API 서비스 환경 > 웹 서비스 URL http://localhost 입력


 `Client ID`와 `Client Secret`을 발급받습니다. 사용 API로 **검색**을 선택합니다.
3. **SMTP 계정**: 메일 공급자의 SMTP 서버 주소, 포트, 로그인 아이디, 비밀번호 또는 앱 비밀번호를 준비합니다. 기본값은 네이버 SMTP(`smtp.naver.com`, 포트 `587`, STARTTLS)입니다. SMTP 사용 설정과 외부 로그인 허용 여부는 메일 공급자에서 미리 확인합니다.
4. **수신자 주소**: 실제 수신자와 시험 발송 수신자 이메일 주소를 준비합니다. 여러 주소는 쉼표로 구분합니다.

> Lambda 환경 변수에 입력한 값은 일반 텍스트 설정값으로 취급될 수 있습니다. 배포 권한과 Lambda 조회 권한을 최소화하고, 비밀번호를 저장소나 배포 ZIP 파일에 넣지 마세요. 이 코드는 현재 AWS Secrets Manager를 직접 읽지 않으므로 Secrets Manager를 사용하려면 별도 코드 변경이 필요합니다.

### 2. AWS 초기 설정

AWS Management Console에 로그인한 뒤 우측 상단 리전을 **서울(ap-northeast-2)** 로 변경합니다. 비용 알림이 필요하면 Billing의 AWS Budgets에서 월간 예산과 이메일 알림도 설정합니다.

콘솔만 사용해도 배포할 수 있습니다. 명령줄 배포도 사용하려면 로컬 PC에 AWS CLI를 설치한 후 다음을 실행합니다.

```powershell
aws configure
```

차례로 Access Key ID, Secret Access Key, 기본 리전 `ap-northeast-2`, 출력 형식 `json`을 입력하고 연결을 확인합니다.

```powershell
aws sts get-caller-identity
```

장기 액세스 키 대신 IAM Identity Center를 사용하는 조직이라면 관리자가 제공한 정보로 `aws configure sso`를 실행한 뒤 `aws sso login`을 사용합니다.

### 3. Lambda 실행 역할 만들기

1. AWS 콘솔에서 **IAM → 역할 → 역할 생성**으로 이동합니다.
2. 신뢰할 수 있는 엔터티 유형은 **AWS 서비스**, 사용 사례는 **Lambda**를 선택합니다.
3. 권한 정책으로 `AWSLambdaBasicExecutionRole`을 연결합니다. 이 정책은 CloudWatch Logs에 실행 로그를 기록할 수 있게 합니다.
4. 역할 이름을 예를 들어 `news-digest-lambda-role`로 지정하고 생성합니다.

이 애플리케이션은 네이버 API와 SMTP 서버에 직접 접속하며 다른 AWS 서비스 권한은 요구하지 않습니다. Lambda를 VPC에 연결하면 인터넷 경로가 사라질 수 있으므로, 특별한 이유가 없다면 VPC에 연결하지 마세요. VPC 연결이 필요하다면 NAT Gateway 등 외부 인터넷 송신 경로가 반드시 있어야 합니다.

### 4. 배포 ZIP 파일 만들기

프로젝트 루트에서 다음 PowerShell 명령을 실행합니다. 현재 `requirements.txt`는 비어 있고 코드는 Python 표준 라이브러리만 사용하므로 별도의 패키지 설치가 필요하지 않습니다.

```powershell
Compress-Archive -Path lambda_function.py,job.py,main.py,news_digest -DestinationPath news-digest.zip -Force
```

ZIP 파일을 열었을 때 최상위에 `lambda_function.py`, `job.py`, `main.py`, `news_digest/`가 보여야 합니다. 이 파일들이 한 단계 아래 폴더에 들어가 있으면 Lambda가 핸들러를 찾지 못합니다.

### 5. Lambda 함수 생성 및 코드 배포

1. AWS 콘솔에서 **Lambda → 함수 생성 → 새로 작성**을 선택합니다.
2. 함수 이름은 예를 들어 `news-digest`로 입력합니다.
3. 런타임은 **Python 3.12 이상**을 선택합니다.
4. 아키텍처는 `x86_64` 또는 `arm64` 어느 쪽이든 사용할 수 있습니다.
5. 실행 역할에서 **기존 역할 사용**을 선택하고 앞에서 만든 `news-digest-lambda-role`을 지정합니다.
6. 함수를 생성한 뒤 **코드 → 업로드 위치 → .zip 파일**에서 `news-digest.zip`을 업로드하고 **저장** 또는 **배포**를 누릅니다.
7. **런타임 설정 → 편집**에서 핸들러를 다음과 같이 지정합니다.

```text
lambda_function.lambda_handler
```

8. **구성 → 일반 구성 → 편집**에서 메모리를 `256 MB`, 제한 시간을 우선 `5분`으로 설정합니다. 검색어가 많아 처리 시간이 긴 경우 CloudWatch 실행 시간을 확인해 조정합니다.

명령줄로 기존 함수의 코드만 갱신하려면 다음을 사용할 수 있습니다.

```powershell
aws lambda update-function-code --function-name news-digest --zip-file fileb://news-digest.zip --region ap-northeast-2
```

### 6. Lambda 환경 변수 설정

**Lambda → news-digest → 구성 → 환경 변수 → 편집**에서 아래 값을 추가합니다.

| 변수 | 필수 | 예시/설명 |
| --- | --- | --- |
| `NAVER_CLIENT_ID` | 예 | 네이버 검색 API Client ID |
| `NAVER_CLIENT_SECRET` | 예 | 네이버 검색 API Client Secret |
| `SMTP_HOST` | 예 | `smtp.naver.com` |
| `SMTP_PORT` | 아니요 | 기본값 `587` |
| `SMTP_USERNAME` | 예 | SMTP 로그인 계정 |
| `SMTP_PASSWORD` | 예 | SMTP 비밀번호 또는 앱 비밀번호 |
| `MAIL_SENDER` | 예 | 발신자 이메일 주소 |
| `REAL_RECIPIENTS` | 운영 시 예 | `user1@example.com,user2@example.com` |
| `TEST_RECIPIENTS` | 시험 시 예 | 시험 메일을 받을 주소 |
| `TEST_MODE` | 아니요 | 시험 수신자에게만 보내려면 `true`, 운영은 `false` |
| `TIMEZONE` | 아니요 | 기본값 `Asia/Seoul` |
| `MAX_ARTICLES` | 아니요 | 전체 최대 기사 수, 기본값 `25` |
| `MIN_SCORE` | 아니요 | 기사 선택 기준값, 기본값 `12` |
| `MMR_LAMBDA` | 아니요 | 관련도와 다양성 균형값, 기본값 `0.70` (`0`~`1`) |
| `USE_SAMPLE_DATA` | 아니요 | 실제 API 대신 샘플 데이터를 쓰려면 `true` |
| `NEWS_QUERIES` | 아니요 | 쉼표로 구분한 검색어. 현재 카테고리별 수집에는 아래 카테고리 변수가 우선 사용됨 |
| `INNODEP_QUERIES` | 아니요 | 이노뎁 카테고리 검색어 목록 |
| `SECURITY_QUERIES` | 아니요 | 보안 카테고리 검색어 목록 |
| `INDUSTRY_QUERIES` | 아니요 | 업계 동향 카테고리 검색어 목록 |
| `GOVERNMENT_QUERIES` | 아니요 | 정부/공공 카테고리 검색어 목록 |
| `VENTURE_QUERIES` | 아니요 | 벤처/금융 카테고리 검색어 목록 |
| `LABOR_QUERIES` | 아니요 | 생산/임금 카테고리 검색어 목록 |
| `KEYWORD_WEIGHTS` | 아니요 | `AI:2,보안:3,CCTV:4` 형식 |
| `CATEGORY_QUOTAS` | 아니요 | `업계 동향 기사:10,보안 관련 기사:4` 형식 |
| `RECOMMENDATION_WEIGHTS` | 아니요 | `rule:0.38,recency:0.08,source:0.02,entity:0.15,language:0.08` 형식 |

처음에는 오발송을 막기 위해 다음처럼 설정하는 것이 안전합니다.

```text
TEST_MODE=true
TEST_RECIPIENTS=본인의_시험용_이메일
REAL_RECIPIENTS=실제_수신자_이메일
```

`TEST_MODE=true`일 때 `TEST_RECIPIENTS`와 `REAL_RECIPIENTS`에 같은 주소가 들어 있으면 안전을 위해 실행이 실패합니다. 시험이 끝나면 `TEST_MODE=false`로 바꿉니다.

### 7. 수동 시험 실행

1. Lambda의 **테스트** 탭에서 새 이벤트를 만듭니다.
2. 이벤트 이름을 `manual-test`로 지정하고 JSON에는 `{}`를 입력합니다.
3. **테스트**를 실행합니다.
4. 성공하면 응답에 `statusCode: 200`과 `News digest sent successfully`가 표시되고 시험 수신자에게 이메일이 도착합니다.

실패하면 **모니터링 → CloudWatch 로그 보기**에서 원인을 확인합니다.

- `NAVER_CLIENT_ID ... required`: 네이버 API 환경 변수를 확인합니다.
- `REAL_RECIPIENTS is required`: 운영 수신자 주소를 입력합니다.
- `TEST_MODE=true requires TEST_RECIPIENTS`: 시험 수신자 주소를 입력합니다.
- SMTP 로그인 오류: SMTP 사용 설정, 계정명, 앱 비밀번호, 발신자 주소가 일치하는지 확인합니다.
- Timeout: Lambda 제한 시간을 늘리고 네이버 API 또는 SMTP 서버의 외부 연결 상태를 확인합니다.

샘플 데이터로 메일 연결만 먼저 확인하려면 `USE_SAMPLE_DATA=true`로 실행합니다. 실제 운영 전에 반드시 `false`로 되돌립니다.

### 8. 매일 자동 실행 설정

EventBridge Scheduler는 시간대를 직접 지정할 수 있어 한국 시간 예약에 편리합니다.

1. AWS 콘솔에서 **Amazon EventBridge → Scheduler → 일정 생성**으로 이동합니다.
2. 일정 이름을 예를 들어 `news-digest-daily`로 입력합니다.
3. 일정 패턴에서 **반복 일정 → Cron 기반 일정**을 선택합니다.
4. 매일 오전 7시 30분에 실행하려면 Cron 표현식에 `cron(30 7 * * ? *)`를 입력하고 시간대를 `Asia/Seoul`로 지정합니다.
5. 유연한 시간 범위는 정확한 시각 실행이 필요하면 **끔**으로 설정합니다.
6. 대상은 **AWS Lambda Invoke**, 함수는 `news-digest`를 선택하고 입력 페이로드는 `{}`로 둡니다.
7. Scheduler 실행 역할은 새 역할 생성을 선택하거나, 해당 Lambda 호출 권한이 있는 기존 역할을 선택합니다.
8. 재시도 정책과 필요 시 DLQ를 설정한 뒤 일정을 활성화합니다.

예약 시각은 뉴스 선별 범위에도 영향을 줍니다. 기본 한국 시간 기준으로 일반 평일에는 전날부터 실행 당일 오전 7시 30분 전까지, 월요일에는 주말을 포함한 최근 범위를 대상으로 합니다.

### 9. 운영과 업데이트

- 실행 내역은 Lambda의 **모니터링** 및 CloudWatch Logs에서 확인합니다.
- 수신자나 검색어 변경은 Lambda 환경 변수만 수정하면 됩니다.
- 코드 변경 후 `news-digest.zip`을 다시 만들고 Lambda 코드에 업로드합니다.
- 같은 일정이 중복 생성되면 메일도 중복 발송될 수 있으므로 활성 일정은 하나만 유지합니다.
- Lambda, CloudWatch Logs, Scheduler에는 사용량에 따른 소액의 비용이 발생할 수 있습니다.

## 개발자 사용 방법: 로컬 환경

### 요구 사항

- Python 3.14 권장
- 네이버 검색 API 인증 정보
- 실제 발송을 시험할 경우 SMTP 계정 정보

이 프로젝트는 현재 외부 Python 패키지를 사용하지 않습니다. 따라서 `requirements.txt` 설치 결과가 비어 있는 것이 정상입니다.

### 1. 가상 환경 준비

Windows PowerShell 기준:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 환경 변수 파일 작성

`.env.sample`을 `.env`로 복사하고 값을 입력합니다. `.env`는 `.gitignore`에 포함되어 있으므로 실제 인증 정보를 커밋하지 마세요.

```powershell
Copy-Item .env.sample .env
```

예시:

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
MAX_ARTICLES=25
MIN_SCORE=12
MMR_LAMBDA=0.70
```

`.env` 로더는 단순한 `KEY=VALUE` 형식을 지원합니다. 여러 수신자와 검색어는 쉼표로 구분합니다.

### 3. 실행 명령

메일을 보내거나 발송 이력을 쓰지 않고 결과만 출력합니다.

```powershell
python main.py --dry-run
```

상세 로그와 함께 미리 봅니다.

```powershell
python main.py --dry-run --verbose
```

뉴스 수집·선별 결과를 JSON 파일로 저장하되 메일은 보내지 않습니다.

```powershell
python main.py --prepare-output prepared-digest.json
```

저장된 JSON을 다시 수집하지 않고 발송합니다.

```powershell
python main.py --send-prepared prepared-digest.json
```

실제 수집과 메일 발송을 한 번에 수행합니다.

```powershell
python main.py
```

처음 개발할 때는 네이버 인증 정보 없이 `.env`에 `USE_SAMPLE_DATA=true`를 지정하고 `--dry-run`으로 렌더링 결과를 확인할 수 있습니다. 실제 발송 명령 전에는 `TEST_MODE=true`와 시험 수신자를 다시 확인하세요.

## 코드 내용 간단 설명

전체 처리 흐름은 다음과 같습니다.

```text
환경 변수 로드
  → 카테고리별 네이버 뉴스 검색
  → 날짜 범위 및 제외 규칙 적용
  → 관련도 점수 계산
  → 카테고리 quota와 MMR로 기사 선택
  → URL·제목 중복 제거
  → 텍스트/HTML 이메일 생성 및 SMTP 발송
```

| 파일 | 역할 |
| --- | --- |
| `lambda_function.py` | AWS Lambda 진입점. `run_job()`을 실행하고 실패 시 Lambda 오류를 발생시킴 |
| `main.py` | 로컬 CLI 진입점. 미리보기, JSON 준비, 준비된 JSON 발송 옵션 제공 |
| `job.py` | 설정 로드부터 수집, 선별, 저장, 렌더링, 발송까지 실행 흐름을 조정 |
| `news_digest/config.py` | `.env` 및 OS 환경 변수를 읽어 `Config` 객체 생성 |
| `news_digest/settings.py` | 기본 검색어, 점수, 기사 수, SMTP 및 추천 기본값 정의 |
| `news_digest/naver.py` | 네이버 뉴스 API 호출, 호출 간격 제한, 429 재시도, 응답 파싱 |
| `news_digest/pipeline.py` | 카테고리별 수집과 추천을 실행하고 카테고리 간 중복 제거 |
| `news_digest/cch_mmr_recommender.py` | 규칙·최신성·출처·엔티티 점수와 MMR을 이용해 관련성과 다양성을 함께 최적화 |
| `news_digest/filters.py` | 날짜 범위, URL/제목 정규화, 중복 제거 및 키워드 기반 보충 선택 |
| `news_digest/categories.py` | 카테고리 순서, 분류 키워드, 언론사 표시 이름 정의 |
| `news_digest/emailer.py` | 텍스트/HTML 본문과 제목을 만들고 STARTTLS SMTP로 발송 |
| `news_digest/models.py` | 기사 데이터 모델 정의 |
| `news_digest/text_similarity.py` | 기사 간 텍스트 및 제목 유사도 계산 |
| `news_digest/keyword_fallback.py` | 주 추천 결과가 없을 때 사용할 키워드 점수 계산 |
| `news_digest/timezones.py` | 시간대 객체 생성과 호환 처리 |

기본 설정을 바꾸지 않고 운영별 값만 조정하려면 코드보다 Lambda 환경 변수 또는 로컬 `.env`를 사용하는 것이 좋습니다.
