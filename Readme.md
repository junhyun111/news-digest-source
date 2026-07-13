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

1. **AWS 계정**: [AWS 계정 생성 페이지](https://aws.amazon.com/ko/)에서 계정을 만듭니다.
2. **네이버 검색 API 애플리케이션**: 다음 순서로 검색 API 사용 신청을 완료합니다.

   1. [네이버 개발자 센터](https://developers.naver.com/)에 접속하여 네이버 계정으로 로그인합니다.
   2. 상단 메뉴에서 **Application → 애플리케이션 등록**으로 이동합니다.
   3. **애플리케이션 이름**에 알아보기 쉬운 임의의 이름(예: `news-digest`)을 입력합니다.
   4. **사용 API**에서 **검색**을 선택합니다.
   5. **비로그인 오픈 API 서비스 환경**에서 **WEB 설정**을 선택합니다.
   6. **웹 서비스 URL**에 `http://localhost`를 입력합니다. 이 프로젝트는 서버에서 비로그인 검색 API를 호출하므로 로컬 URL을 등록값으로 사용할 수 있습니다.
   7. 약관을 확인하고 **등록하기**를 누릅니다.
   8. 등록이 완료되면 **Application → 내 애플리케이션 → 등록한 애플리케이션**으로 이동합니다.
   9. **개요** 또는 **인증 정보** 화면에 표시되는 `Client ID`와 `Client Secret`을 복사하여 안전한 곳에 보관합니다. 이후 Lambda 환경 변수의 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`에 각각 입력합니다.

   `Client Secret`은 비밀번호와 같은 인증 정보이므로 README, 소스 코드, `.env.sample` 또는 배포 ZIP에 직접 기록하거나 외부에 공유하지 마세요.

3. **네이버 메일 SMTP 계정**: 네이버 계정의 일반 비밀번호 대신 애플리케이션 비밀번호를 생성하여 SMTP 인증에 사용합니다.

   1. [네이버](https://www.naver.com/)에 접속하여 발신에 사용할 네이버 계정으로 로그인합니다.
   2. 로그인 영역의 프로필 또는 네이버 ID를 누른 뒤 **네이버ID → 보안설정**으로 이동합니다.
   3. **2단계 인증** 항목에서 **관리**를 누릅니다. 2단계 인증이 설정되어 있지 않다면 먼저 휴대전화 인증을 거쳐 2단계 인증을 설정합니다.
   4. 2단계 인증 관리 화면에서 **애플리케이션 비밀번호 관리** 항목으로 이동합니다.
   5. **애플리케이션 비밀번호 생성**에서 애플리케이션 종류를 선택합니다. 직접 입력할 수 있다면 `news-digest`와 같이 알아보기 쉬운 이름을 입력합니다.
   6. **생성하기**를 누릅니다.
   7. 화면에 표시된 애플리케이션 비밀번호를 즉시 복사하여 안전한 곳에 보관합니다. 이 비밀번호는 SMTP 인증에 사용하며, 네이버 계정의 일반 로그인 비밀번호는 사용하지 않습니다.
   8. 이 프로젝트에서는 다음 SMTP 값을 사용합니다.

      | 설정 | 입력값 |
      | --- | --- |
      | SMTP 서버명 | `smtp.naver.com` |
      | SMTP 포트 | `587` |
      | 보안 연결 | STARTTLS |
      | 사용자 이름 | 네이버 메일 주소(예: `naver_id@naver.com`) |
      | 비밀번호 | 앞 단계에서 생성한 애플리케이션 비밀번호 |
      | 발신자 주소 | 로그인한 계정의 네이버 메일 주소(예: `naver_id@naver.com`) |

   9. 준비한 값은 이후 Lambda 환경 변수에 다음과 같이 입력합니다.

      ```text
      SMTP_HOST=smtp.naver.com
      SMTP_PORT=587
      SMTP_USERNAME=naver_id@naver.com
      SMTP_PASSWORD=생성한_애플리케이션_비밀번호
      MAIL_SENDER=naver_id@naver.com
      ```

   애플리케이션 비밀번호는 생성 직후에만 확인할 수 있으므로 안전하게 보관하세요. 노출되었거나 분실한 경우 기존 비밀번호를 삭제하고 새로 생성합니다. 이 값은 `Client Secret`과 마찬가지로 README, 소스 코드, `.env.sample` 또는 배포 ZIP 파일에 기록하지 마세요.

4. **수신자 주소**: 실제 수신자와 시험 발송 수신자 이메일 주소를 준비합니다. 여러 주소는 쉼표로 구분합니다.

> Lambda 환경 변수에 입력한 값은 일반 텍스트 설정값으로 취급될 수 있습니다. 배포 권한과 Lambda 조회 권한을 최소화하고, 비밀번호를 저장소나 배포 ZIP 파일에 넣지 마세요. 이 코드는 현재 AWS Secrets Manager를 직접 읽지 않으므로 Secrets Manager를 사용하려면 별도 코드 변경이 필요합니다.

### 2. AWS 초기 설정

다음 순서로 AWS 콘솔에 로그인하고 작업 리전을 서울로 설정합니다.

1. [AWS Management Console](https://console.aws.amazon.com/)에 접속합니다.
2. 사용할 AWS 계정으로 로그인합니다.
3. 콘솔 화면 오른쪽 위에 표시되는 **리전 이름**을 누릅니다.
4. 리전 목록에서 **아시아 태평양(서울) `ap-northeast-2`** 을 선택합니다.
5. Lambda와 EventBridge를 설정하는 동안 화면 오른쪽 위에 **서울**이 표시되는지 확인합니다.

### 3. Lambda 실행 역할 만들기

Lambda가 실행 로그를 CloudWatch Logs에 기록할 수 있도록 전용 IAM 역할을 만듭니다.

1. AWS 콘솔 위쪽 검색창에 `IAM`을 입력하고 검색 결과에서 **IAM**을 선택합니다.
2. IAM 화면 왼쪽 메뉴에서 **액세스 관리 → 역할**을 선택합니다.
3. 오른쪽 위의 **역할 생성**을 누릅니다.
4. **신뢰할 수 있는 엔터티 유형**에서 **AWS 서비스**를 선택합니다.
5. **서비스 또는 사용 사례**에서 `Lambda`를 검색하고 **Lambda**를 선택한 뒤 **다음**을 누릅니다.
6. **권한 정책** 검색창에 `AWSLambdaBasicExecutionRole`을 입력합니다.
7. `AWSLambdaBasicExecutionRole` 왼쪽의 확인란을 선택하고 **다음**을 누릅니다. 이 정책은 Lambda 실행 로그를 CloudWatch Logs에 기록할 수 있게 합니다.
8. **역할 이름**에 `news-digest-lambda-role`을 입력합니다.
9. 신뢰할 수 있는 엔터티에 `lambda.amazonaws.com`, 권한에 `AWSLambdaBasicExecutionRole`이 표시되는지 검토합니다.
10. 화면 아래의 **역할 생성**을 누릅니다.
11. 역할 목록에서 `news-digest-lambda-role`을 검색하여 정상적으로 생성되었는지 확인합니다.

이 애플리케이션은 네이버 API와 SMTP 서버에 직접 접속하며 다른 AWS 서비스 권한은 요구하지 않습니다. Lambda를 VPC에 연결하면 인터넷 경로가 사라질 수 있으므로, 특별한 이유가 없다면 VPC에 연결하지 마세요. VPC 연결이 필요하다면 NAT Gateway 등 외부 인터넷 송신 경로가 반드시 있어야 합니다.

### 4. 배포 ZIP 파일 만들기

Lambda에는 Python 파일을 하나씩 올리지 않고, 실행에 필요한 파일과 폴더를 하나의 ZIP 파일로 만들어 업로드합니다. 현재 `requirements.txt`는 비어 있고 Python 표준 라이브러리만 사용하므로 별도의 패키지 설치는 필요하지 않습니다.

Windows에서 다음 순서로 배포 파일을 만듭니다.

1. 파일 탐색기에서 이 프로젝트가 저장된 `news-digest-source` 폴더를 엽니다.
2. 탐색기 주소 표시줄에 `powershell`을 입력하고 Enter를 누릅니다. 현재 프로젝트 폴더를 기준으로 PowerShell이 열립니다.
3. 다음 명령을 실행합니다.

   ```powershell
   Compress-Archive -Path lambda_function.py,job.py,main.py,news_digest -DestinationPath news-digest.zip -Force
   ```

4. 프로젝트 폴더에 `news-digest.zip`이 생성되었는지 확인합니다.
5. `news-digest.zip`을 열었을 때 첫 화면에 다음 파일과 폴더가 바로 표시되는지 확인합니다.

   ```text
   news-digest.zip
   ├─ lambda_function.py
   ├─ job.py
   ├─ main.py
   └─ news_digest/
   ```

   `news-digest-source/` 폴더가 ZIP 안에 통째로 들어가고 Python 파일이 그 아래에 있으면 잘못 압축된 것입니다. `lambda_function.py`가 ZIP 최상위에 없으면 Lambda가 핸들러를 찾지 못합니다.

6. ZIP을 다시 만들 때는 같은 명령을 실행합니다. `-Force` 옵션이 기존 `news-digest.zip`을 새 파일로 교체합니다.

> `.env`, `.venv`, `__pycache__`, 실제 비밀번호 또는 개발용 데이터 파일은 배포 ZIP에 포함하지 마세요.

### 5. Lambda 함수 생성 및 코드 배포

다음 순서로 Lambda 함수를 만들고 앞에서 생성한 ZIP 파일을 배포합니다.

#### 5-1. Lambda 함수 만들기

1. AWS 콘솔 위쪽 검색창에 `Lambda`를 입력하고 검색 결과에서 **Lambda**를 선택합니다.
2. 화면 오른쪽 위의 리전이 **서울**인지 다시 확인합니다.
3. 왼쪽 메뉴에서 **함수**를 선택하고 오른쪽 위의 **함수 생성**을 누릅니다.
4. 함수 생성 방식에서 **새로 작성**을 선택합니다.
5. **기본 정보**에 다음 값을 입력합니다.

   | 설정 | 선택 또는 입력값 |
   | --- | --- |
   | 함수 이름 | `news-digest` |
   | 런타임 | `Python 3.12` 이상 |
   | 아키텍처 | `x86_64` |

6. **기본 실행 역할 변경**을 펼칩니다.
7. **실행 역할**에서 **기존 역할 사용**을 선택합니다.
8. **기존 역할** 목록에서 `news-digest-lambda-role`을 선택합니다.
9. 나머지 항목은 기본값으로 두고 **함수 생성**을 누릅니다.
10. 함수 상세 화면 상단에 초록색 성공 메시지가 표시될 때까지 기다립니다.

#### 5-2. Python ZIP 파일 업로드하기

1. Lambda 왼쪽 메뉴의 **함수**에서 방금 만든 `news-digest`를 선택합니다.
2. 함수 상세 화면에서 **코드** 탭을 선택합니다.
3. **코드 소스** 영역 오른쪽의 **업로드 위치**를 누릅니다.
4. 메뉴에서 **.zip 파일**을 선택합니다.
5. 파일 선택 창에서 프로젝트 폴더의 `news-digest.zip`을 선택하고 **열기**를 누릅니다.
6. 업로드 창에서 **저장**을 누릅니다.
7. 업로드가 완료된 뒤 코드 소스의 파일 목록에 `lambda_function.py`, `job.py`, `main.py`, `news_digest`가 표시되는지 확인합니다.

#### 5-3. Lambda 핸들러 설정하기

1. 같은 함수 화면의 **코드** 탭에서 아래쪽 **런타임 설정** 영역을 찾습니다.
2. **편집**을 누릅니다.
3. **핸들러** 입력값을 다음과 같이 변경합니다.

   ```text
   lambda_function.lambda_handler
   ```

4. **저장**을 누릅니다.

`lambda_function`은 ZIP 최상위의 `lambda_function.py` 파일 이름이고, `lambda_handler`는 파일 안에서 Lambda가 호출할 함수 이름입니다.

#### 5-4. 메모리와 제한 시간 설정하기

1. 함수 상세 화면에서 **구성** 탭을 선택합니다.
2. 왼쪽 메뉴에서 **일반 구성**을 선택합니다.
3. **편집**을 누릅니다.
4. **메모리**에 `2048 MB`를 입력합니다.
5. **제한 시간**을 `15분 0초`로 설정합니다.
6. **저장**을 누릅니다.

검색어가 많아 실행이 끝나지 않으면 CloudWatch Logs의 실행 시간을 확인한 뒤 제한 시간을 조정합니다. 네이버 API와 SMTP 서버에 접속해야 하므로 **구성 → VPC**는 기본값인 VPC 연결 없음 상태로 둡니다.

#### 5-5. 수정된 Python 파일 다시 배포하기

코드를 수정한 후에는 다음 순서로 Lambda 코드를 업데이트합니다.

1. 프로젝트 폴더에서 `Compress-Archive` 명령을 다시 실행하여 `news-digest.zip`을 새로 만듭니다.
2. AWS 콘솔에서 **Lambda → 함수 → news-digest → 코드**로 이동합니다.
3. **코드 소스 → 업로드 위치 → .zip 파일**을 선택합니다.
4. 새로 만든 `news-digest.zip`을 선택한 뒤 **저장**을 누릅니다.
5. 업로드 성공 메시지를 확인한 후 수동 테스트를 실행합니다.

### 6. Lambda 환경 변수 설정

네이버 API 인증 정보, SMTP 애플리케이션 비밀번호, 수신자 주소를 Lambda 환경 변수에 등록합니다.

1. AWS 콘솔에서 **Lambda → 함수 → `news-digest`**로 이동합니다.
2. 함수 상세 화면에서 **구성** 탭을 선택합니다.
3. 왼쪽 메뉴에서 **환경 변수**를 선택합니다.
4. 오른쪽의 **편집**을 누릅니다.
5. **환경 변수 추가**를 누르면 나타나는 **키**와 **값** 입력란에 아래 표의 변수를 한 줄씩 등록합니다.
6. 필수 변수를 모두 입력한 뒤 화면 아래의 **저장**을 누릅니다.
7. 환경 변수 목록에 입력한 키가 표시되는지 확인합니다. 인증 정보의 실제 값은 화면 공유나 문서에 노출하지 마세요.

| 변수 | 필수 | 예시/설명 |
| --- | --- | --- |
| `NAVER_CLIENT_ID` | 예 | 네이버 검색 API Client ID |
| `NAVER_CLIENT_SECRET` | 예 | 네이버 검색 API Client Secret |
| `SMTP_HOST` | 예 | `smtp.naver.com` |
| `SMTP_PORT` | 아니요 | 기본값 `587` |
| `SMTP_USERNAME` | 예 | 네이버 메일 주소(예: `naver_id@naver.com`) |
| `SMTP_PASSWORD` | 예 | 네이버 보안설정에서 생성한 애플리케이션 비밀번호 |
| `MAIL_SENDER` | 예 | `SMTP_USERNAME`과 같은 네이버 메일 주소 |
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
8. **일정 생성**을 누르고 일정이 **활성화됨** 상태인지 확인합니다.

예약 시각은 뉴스 선별 범위에도 영향을 줍니다. 기본 한국 시간 기준으로 일반 평일에는 전날부터 실행 당일 오전 7시 30분 전까지, 월요일에는 주말을 포함한 최근 범위를 대상으로 합니다.

### 9. 운영과 업데이트

- 실행 내역은 Lambda의 **모니터링** 및 CloudWatch Logs에서 확인합니다.
- 수신자나 검색어 변경은 Lambda 환경 변수만 수정하면 됩니다.
- 코드 변경 후 `news-digest.zip`을 다시 만들고 Lambda 코드에 업로드합니다.
- 같은 일정이 중복 생성되면 메일도 중복 발송될 수 있으므로 활성 일정은 하나만 유지합니다.

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
