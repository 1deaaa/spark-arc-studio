# Matchbox 에이전트 게이트웨이 — 에이전트를 위한 풀스택 대형 모델 게이트웨이
[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

![MatchGateway App](./app.png)

Matchbox 에이전트 게이트웨이(Matchbox Agent Gateway)는 에이전트(Agent) 개발을 위해 설계된 강력하고 유연한 대형 모델 라우팅 및 쿼터 제어 센터입니다. **경량화되어 별도의 복잡한 배포가 필요 없으며, 에이전트 개발 및 관리 파이프라인에 깊이 통합됩니다.** 오늘날 가장 널리 쓰이는 에이전트 오케스트레이션 프레임워크인 **LangChain 및 LangGraph**에 맞춰 설계되었지만, **AutoGen, CrewAI 등 다른 에이전트 프레임워크로도 매우 쉽게 이식할 수 있습니다.** 코딩 어시스턴트에게 한 문장으로 지시하기만 하면 프레임워크에 맞춘 어댑터 작성이 가능합니다.

이 프로젝트는 개인 개발/디버깅 단계부터 멀티 테넌트 프로덕션 환경에 이르기까지 다양한 복잡한 시나리오를 지원하며, 핵심 설정 관리를 단순화하기 위한 그래픽 사용자 인터페이스(GUI)를 기본 탑재하고 있습니다.

> 💡 **왜 "성냥(Matchbox)"인가요?**
> 성냥은 스마트의 불씨를 지피는 원재료입니다. AI 대중화 시대에 AI 서비스를 구축하는 운영자들은 마치 "성냥 파는 소녀"와도 같은 고충을 겪곤 합니다(~~Token이 잘 팔리지 않으니 도와주세요~~).
> ![MatchGateway Slogan](./slogan.jpg)

### 🔥 왜 빌트인 내장형 게이트웨이인가요?

NewAPI, LiteLLM 등 전용 외부 게이트웨이도 강력하지만, 복잡한 애플리케이션과 직접 통합할 때는 종종 연동 흐름이 끊기는 단점이 있습니다. 본 매니저는 **애플리케이션 내장형 게이트웨이**로서 다음과 같은 독보적인 강점을 제공합니다:

1. **에이전트 오케스트레이션 생태계와의 직접적인 통합**:
   내장 게이트웨이는 애플리케이션의 코드 레이어에서 직접 동작합니다. 따라서 에이전트 오케스트레이션 과정에서의 컨텍스트, 도구 호출(Function Calling) 선언, 특수 구조화 출력 포맷 등을 심리스하게 전달합니다. 외부 게이트웨이의 여러 홉(Hop) 전달로 발생하는 네트워크 지연 및 긴 연결 끊김 현상을 예방하며, 스트리밍 응답 프록시 시 발생하는 프로토콜 호환성 소실 문제를 원천 방어합니다.
2. **"시스템 관리"와 "사용자 소유 Key (BYOK)"의 유연한 공존**:
   상용화 및 일반 사용자 대상의 멀티 테넌트 시나리오를 완벽하게 보장합니다. **시스템 관리형**(어드민이 전역 대형 모델 풀을 설정하고 사용자는 즉시 호출)과 **사용자 소유 Key(Bring Your Own Key)** 방식을 모두 제공합니다. 사용자 Key 데이터의 암호화 격리가 애플리케이션 내부에서 완료되므로, 별도의 게이트웨이 시스템을 오가며 번거롭게 계정을 동기화하고 토큰을 발급받을 필요가 없습니다.
3. **네이티브급 다차원配額(Quota) 통제**:
   강력한 사용량 제한 메커니즘이 포함되어 있습니다. 시스템은 애플리케이션 자체의 User ID에 결합되어 "시스템 차감형"(운영자 Key 소모)과 "사용자 자비형"(BYOK 소모) 호출을 명확하고 자동적으로 구분하며, 두 트랙의 한도를 별도 관리합니다. 이를 통해 원격 API 서버로 요청이 전달되기 직전에 로컬에서 즉시 한도 초과 여부를 정밀 판정하고 차단할 수 있습니다.
4. **통합 운영, 일관된 극대 경량화**:
   별도의 Redis 캐시 서버를 띄우거나 OneAPI 등 복잡한 Docker 컨테이너를 복합 배포할 필요가 없습니다. 과금 정산, 감사 로그, 모델 제어, 사용량 통계 등의 모든 기능이 본 컴포넌트 내에 내장된 SQLite 및 SQLAlchemy를 통해 우아하게 해소되므로 로컬 개발 디버깅과 프라이빗 배포의 운영 부담을 크게 덜어줍니다.

## ✨ 핵심 기능

- **다양한 실행 모드**:
   - **글로벌 싱글 유저 모드**: 백엔드 서비스, 개인 생산성 도구 또는 개발 디버깅 시 적합합니다. 환경 변수로 지정된 전역 모델로 모든 요청이 수렴합니다.
   - **멀티 유저 고정 플랫폼 모드**: 모델의 신뢰성과 출처를 강제해야 하는 보안 서비스에 유용합니다. 모든 사용자는 관리자가 고정한 플랫폼만을 사용하되, 각자 발급받은 개인 API Key를 적용해 구동합니다.
   - **멀티 유저 커스텀 플랫폼 모드**: 최상의 유연성을 제공합니다. 개별 사용자가 스스로 원하는 LLM 플랫폼과 모델 식별자를 입력하고 관리할 수 있습니다.
- **단일화된 호출 인터페이스**: 백엔드 설정이 어떻게 바뀌든 개발자는 코드 단에서 `matchbox().get_user_llm(user_id, usage_key="fast")` 한 줄로 사용자의 성향에 타게팅된 LLM 인스턴스를 즉시 획득합니다.
- **스마트 추론 스트림 필터링 (대기 제거)**: 게이트웨이는 **OpenAI 규격 프로토콜과 호환**되며, 호출 도중 추론 모델들이 출력하는 특수 생각 필드(예: `reasoning_content` 혹은 `<think>` 마크업 태그)를 실시간 감지하여 **통합 스트리밍 텍스트로 보정 송출**합니다. 따라서 프론트엔드는 생각 사슬이 기동하는 동안에도 끊김 없이 부드러운 스트리밍 로딩 텍스트를 연출할 수 있습니다.
- **다용도 타겟팅 슬롯**: 사용자별로 "메인 모델 (Main) / 빠른 모델 (Fast) / 추론 모델 (Reason)" 등의 타겟팅 슬롯을 제공하며, 필요한 경우 사용자가 커스텀 슬롯을 추가해 임의의 모델에 바인딩할 수 있습니다.
- **시스템 영역과 사용자 영역의 철저한 격리**: "공용 시스템 플랫폼"과 "사용자 개별 플랫폼"을 분리 관리합니다. 공용 플랫폼 정보는 YAML 파일(`matchbox_cfg.yaml`)로 관리되고, 사용자 플랫폼 정보는 데이터베이스에 영구 보존됩니다.
- **안전한 API Key 관리**:
   - 하드코딩 유출 예방을 위해 **환경 변수**를 통한 API Key 매핑 관리를 강력 권장합니다.
   - 사용자가 공용 플랫폼에 자신만의 API Key를 오버라이드 등록하여 호출 비용을 개별 분담할 수 있습니다.
   - `LLM_AUTO_KEY` 옵션을 통해 사용자의 Key가 없을 때 서버의 공용 결제 Key로 자율 폴백 기동하도록 제어할 수 있습니다. (과비용 청구 예방을 위해 설정에 신중해야 합니다).
- **자금 소모 트랙별配額(Quota) 필터**:
   - API 호출은 소모 비용 귀속에 맞춰 `sys_paid`(운영자 Key 차감)와 `self_paid`(사용자 소유 Key 차감)로 나뉘어 집계됩니다.
   - 두 트랙 각각 "N시간당 호출 한도" 및 "누적 한도"를 개별 설정하고 통제할 수 있습니다.
- **리딤 코드(Redeem Code) 패키지**:
   - 어드민은 리딤 코드를 대량 발행, 폐기, 관리할 수 있으며 충전 성냥(크레딧) 액수를 지정합니다.
   - 2가지 유형 제공: `single`(선착순 1인 사용 즉시 소멸), `per_user`(사용자별로 각 1회씩 등록 가능한 공용 쿠폰).
   - 리딤 코드는 오타 유방 문자를 배제한 20자리 난수 문자열로 자동 생성되며, 원할 경우 임의의 문구로 커스텀 발행할 수 있습니다.
- **액티브 원격 모델 탐색**: 독립된 탐색 도구(`probe_platform_models`)를 가동하여 OpenAI 표준 명세 호환 API를 지닌 원격 타깃 플랫폼의 호출 가능 모델 리스트를 즉시 쿼리해 옵니다.
- **추론 및 정산 필드 투명성 (플랫폼 테스팅)**: GUI 개발 도구의 "모델 테스트"창에서 수신된 날것의 원본 Response JSON을 로깅해 보여줍니다. DeepSeek 등 플랫폼이 반환하는 `reasoning_content`, `usage`, `billing` 원본 구조를 한눈에 볼 수 있습니다.
- **시각화 설정 헬퍼**: `Tkinter` 기반의 데스크톱 관리 도구(`matchbox_cfg_gui.py`)를 내장하고 있어, 별도 웹 정적 파일 배포 없이도 **로컬 SQLite에 직접 접근**하여 플랫폼/모델 리스트 수정, API Key 암호화 보관, 모델 성능 테스트, 마이그레이션 백업 파일 추출(YAML 백업)을 지원합니다.
- **데이터베이스 보존**: 신뢰성 높은 로컬 경량 데이터 저장 장치인 SQLite를 이용해 사용량과 설정을 안전하게 누적 보존합니다.
- **자율 예외 자가 복구**: 사용자가 타겟팅해 둔 특정 플랫폼이나 모델 데이터가 데이터베이스에서 유실된 경우, 게이트웨이가 작동 시점에 첫 번째 유효 모델을 찾아 자동으로 폴백하여 서비스가 뻗는 에러를 예방합니다.

## 📂 파일 및 디렉터리 구성

```
.
├── __init__.py            # 패키지 진입부, initialize_matchbox / matchbox / create_matchbox 내보냄
├── manager.py             # AIManager 핵심 메인 제어 모듈 (모든 Mixin 통합)
├── config.py              # 전역 환경 설정 매핑 (USE_SYS_LLM_CONFIG, LLM_AUTO_KEY 등)
├── models.py              # SQLAlchemy 데이터베이스 스키마 정의
├── security.py            # 대칭키 암호화 보안 제어부 (SecurityManager)
├── admin.py               # 플랫폼 및 모델 구조 제어 Mixin (AdminMixin)
├── builder.py             # LangChain 객체 인스턴스 빌드 Mixin (LLMBuilderMixin)
├── user_services.py       # 사용자 기초 서비스 Mixin (UserServicesMixin)
├── quota_services.py      # 한도配額 설정, 누적 사용량 판정 Mixin (QuotaServicesMixin)
├── usage_services.py      # 시계열 통계 및 사용량 적재 Mixin (UsageServicesMixin)
├── redeem_code_services.py # 리딤 코드 발행 및 사용 처리 Mixin (RedeemCodeServicesMixin)
├── tracked_model.py       # LLMClient / LLMUsage / 콜백 트래킹 래퍼 클래스
├── estimate_tokens.py     # 로컬 토큰 카운팅 연산 헬퍼 (tiktoken 기반 CJK 보정)
├── utils.py               # 유틸 헬퍼 (probe_platform_models, parse_extra_body 등)
├── matchbox_cfg.yaml       # 공용 플랫폼 사전 초기화 명세 (최초 시동 시에만 데이터베이스에 로드)
├── matchbox_cfg_gui.py     # 로컬 GUI 설정 도구 진입점 (실제 동작은 gui/ 내부 코드 가동)
├── gui/                   # GUI 세부 컴포넌트 폴더
│   ├── __init__.py
│   ├── main_window.py     # 메인 화면 설계 클래스 (플랫폼, 모델 일람, 로그 영역)
│   ├── platform_panel.py  # 플랫폼 편집 패널
│   ├── model_panel.py     # 모델 추가 패널
│   ├── dialogs.py         # 다이얼로그 모듈 (한도 설정, 역할 지정 등)
│   ├── key_manager.py     # API Key 등록 제어부
│   ├── probe.py           # 커넥션 확인 및 추론 성능 로깅 모듈
│   ├── dpi.py             # 운영체제 고해상도 DPI 폰트 및 윈도우 스냅 스케일링
│   └── theme.py           # GUI 색상 팔레트 및 테이블 데코레이션
├── llm_config.db          # (자동 생성) SQLite 로컬 데이터베이스 파일
└── README.md              # 본 안내 문서
```

- **`manager.py`**: 단일 `AIManager` 클래스를 구성하고 있으며, 코드 가독성과 유지보수성을 극대화하기 위해 Mixin 기법으로 각 기능 서브 클래스들을 병합하고 있습니다. 플랫폼 인터페이스 호출의 핵심 통로입니다.
- **`quota_services.py`**: 한도 관리 중추로서, `sys_paid` 및 `self_paid` 두 트랙의 시간대 슬라이딩 윈도우 한도 계산과 호출 전 검증(Pre-flight Check)을 전담합니다.
- **`usage_services.py`**: 사용량 분석 로그 적재를 담당합니다.
- **`matchbox_cfg.yaml`**: **기본 데이터 로드용 YAML 명세**입니다. 데이터베이스가 텅 비어 있는 최초 구동 단계에서 이 명세의 내용들을 SQLite DB에 적재합니다. 이후 재부팅 시에는 신규 누적 데이터만 점진적으로 적재하고 기존 커스텀 수정 사항은 덮어쓰지 않습니다. **따라서 런타임 시 실제 설정의 진실원은 DB 파일이며 이 YAML 파일이 아닙니다.**
- **`matchbox_cfg_gui.py`**: GUI 실행용 진입 스크립트입니다. DB 파일에 직접 입출력하며, CLI 개발 환경에서도 에전에 쓰인 키 암호화 관리, 모델 핑 테스트 등을 웹 구동 없이 다룰 수 있습니다.

## 🛠️ 최초 연동 가이드 (필독)

**주의사항:** 저장소에 내장된 기본 파일(`matchbox_cfg.yaml`)은 로컬 테스트 및 설정 규격 공유 목적이며, 내부에 기입된 암호화된 API Key 문자열(`ENC:...`)은 최초 배포자 컴퓨터의 고유 마스터 키로 감싸여 있으므로 귀하의 로컬 환경에서는 복호화되지 않는 것이 정상입니다.

원활한 사용을 위해 본인의 유효한 API Key로 수정 등록해야 합니다:

1. **마스터 키 지정 (LLM_KEY)**:
    - 시스템은 로컬에 보안 저장되는 모든 API Key를 암호화하기 위해 `LLM_KEY`를 사용합니다. 시스템 환경 변수로 등록하거나 GUI 실행 시 팝업을 통해 기입하여 보존하십시오.
    - **최초 실행 시 "복호화 실패 키 감지" 경고창이 뜨더라도 당황하지 마십시오.** 단순히 배포판 YAML 내의 다른 환경 키가 탐지되었음을 의미합니다. 본인의 새 마스터 키 `LLM_KEY`를 새로 지정한 후 경고창 안내에 따라 "유효하지 않은 기존 키 일괄 삭제" 버튼을 눌러 정리하십시오. **이 작업은 데이터 테이블 구조를 건드리지 않고 유효 불가능한 기존 암호문 필드만 청소합니다.**

2. **설정 GUI 실행**:
    - CLI 터미널 환경에서 `server/llm/agen_matchbox` 위치로 이동하여 다음 명령을 구동합니다:
      `python matchbox_cfg_gui.py`
    - DeepSeek 등 예시 플랫폼 노드가 표시되나 Key가 잠겨 있는 상태를 볼 수 있습니다.

3. **API Key 대입 및 보존**:
    - 사용하고자 하는 플랫폼 노드를 리스트에서 클릭한 뒤, 우측 입력 영역에 실제 발급받은 유효한 **API Key** 값을 채우고 저장 버튼을 클릭합니다.
    - 사용 계획이 없는 플랫폼 노드는 삭제하여 구조를 정리해 줍니다.

4. **원격 모델 확보**:
    - 우측 하단의 **"원격 모델 탐색 (Probe)"** 버튼을 클릭합니다. 연동 상태에 예외가 없다면 원격 엔드포인트에서 지원하는 구체적인 모델 사양이 노출됩니다.
    - 사용을 희망하는 특정 모델을 더블클릭하거나 추가 버튼을 눌러 내 리스트에 올립니다.

5. **기본 용도 매핑 확인**:
    - 상단 메뉴의 **"시스템 용도 관리"** 버튼을 켭니다.
    - 내 서비스의 `main` (대표 모델), `fast` (빠른 모델), `reason` (생각 추론 모델) 슬롯이 방금 API Key를 정상 등록한 실제 동작 모델에 바인딩되어 있는지 체크합니다.

6. **연동 검증**:
    - 모델 노드를 클릭한 뒤 **"모델 테스트"** 버튼을 클릭해 정상적으로 텍스트 응답이 출력되는지 로깅을 확인합니다.
    - 콘솔에 성공 로그가 표시되면 게이트웨이 기초 셋업이 완수된 것입니다.

## ⚙️ 설계 철학 및 작동 모드

개발 기획 및 에이전트 확장 전 아래의 라우팅 구조와 모드 설정을 파악해야 올바른 에이전트 커넥터 작성이 가능합니다.

### 표준 아키텍처 구성 (권장 사항)

Matchbox 게이트웨이는 시스템의 견고함과 런타임 격리 수준을 방어하기 위해 다음과 같이 듀얼 채널(Dual-Channel)로 작동합니다:

1. **관리 제어 채널 (Default Admin Channel)**:
   - 서버 구동 초입 단계에서 `initialize_matchbox(ensure_defaults=True)` 함수를 명시적으로 최초 1회 트리거하여 기본 데이터 동기화를 완료합니다.
   - 요청 시에는 전역 싱글톤인 `matchbox()` 매니저를 호출해 `get_user_llm(...)` 또는 `get_user_embedding(...)`을 통해 통신 인스턴스를 뽑아냅니다.
   - 계정 등급별 지정 모델 필터, API Key 교차 판정, 한도 락 및 시계열 로깅이 자동 개입합니다.
2. **패스스루 채널 (Passthrough Quick Channel)**:
   - 가벼운 원타임 스크립트 작성이나 임시 태스크를 소화할 때는 `create_quick_llm(...)` 또는 `create_quick_embedding(...)` 함수를 직접 호출해 클라이언트를 획득합니다.
   - 이 경로는 로컬 데이터베이스 연동과配額 검사를 완전히 통과하므로 복잡한 DB 트랜잭션 종속이 없습니다.
3. **생명주기 안전선**:
   - 시스템 기동 시 초기화하고, 서비스 종료 시점에 `reset_matchbox()`를 타게 함으로써 모듈 임포트 자체로 인한 부팅 사이드 이펙트(오염)를 차단합니다.
4. **홈 디렉터리 통제**:
   - 환경 변수 `AGENT_MATCHBOX_HOME`을 이용해 DB 파일, `.env` 키 파일, YAML 설정 문서의 적재 디스크 물리 위치를 단일 포인트로 통제합니다.

### 코드 연동 프로토타입 예시

```python
from llm.agen_matchbox import initialize_matchbox, matchbox

# 1) 백엔드 기동 라이프사이클 이벤트 단에서 1회 작동
initialize_matchbox(ensure_defaults=True)

# 2) API 요청 핸들러 내부에서 해당 계정 컨텍스트에 매칭해 인스턴스 획득
client = matchbox().get_user_llm(
    user_id="user_123", 
    usage_key="main", 
    agent_name="agent_director"
)

# 3) 표준 LangChain 인터페이스와 동일하게 연산 처리
result = client.invoke("사이버펑크 세계관 기획 초안을 설계해 줘.")

# 4) 스트리밍 토크나이저도 동일하게 작동하며, 완료 시 토큰 사용량이 백그라운드 적재됩니다.
for chunk in client.stream("3막 구조로 아웃라인을 전개해 줘."):
    print(chunk.content, end="")
```

### 1. 가상 마스터 유저 (`SYSTEM_USER_ID = "-1"`)

내부적으로 지정된 특수 사용자 식별값입니다. 계정 ID가 누락되었거나 `-1`로 쿼리된 경우 매니저는 즉시 **시스템 기본 모드**로 진입합니다.

- **역할**: 백엔드 자체 청소 태스크, 비로그인 일반 API, 테스트 기동 시 전역 공용 모델 인스턴스를 즉시 뿜어주는 폴백 채널입니다.
- **Key 획득 우선순위**: 시스템 모드 기동 시 어드민이 공용 설정에 기입한 시스템 결제 마스터 API Key를 탑재하며, 부재 시 환경 변수에서 로드된 시스템 기본 Key 규격을 준수합니다.

### 2. 고정 플랫폼과 자유 편집의 장벽

[`config.py`](config.py) 명세에 기술된 주요 모드 조작 플래그입니다:

- **`USE_SYS_LLM_CONFIG = True` (멀티 유저 고정 플랫폼 모드)**
  - 일반 가입자는 어드민이 구성해 둔 공용 시스템 AI 플랫폼 종류와 모델 이름 리스트만 볼 수 있습니다.
  - 일반 계정 레벨에서 플랫폼을 임의 추가하거나 지우는 DDL 권한이 **차단**됩니다.
  - 다만, 공용 플랫폼 노드에 자신만의 API Key를 개별 등록(`llm_sys_platform_keys` 테이블에 보안 결합)하여 호출 요금을 스스로 소모하게 제어할 수 있습니다.
  - 가입자의 유연성은 보장하되 공용 모델 규격을 고정하는 엔터프라이즈 환경에 매치합니다.
- **`USE_SYS_LLM_CONFIG = False` (멀티 유저 자유 플랫폼 모드) [기본값]**
  - 일반 가입자에게 개별 플랫폼 추가 권한을 활짝 열어줍니다.
  - 사용자 고유의 플랫폼 데이터와 엔드포인트 주소는 데이터베이스의 개별 계정 테이블 영역에 프라이빗 보존되며 타인에게 공유되지 않습니다.

### 3. API Key 대치 탐색 논리 및 `LLM_AUTO_KEY`

호출 인스턴스 생성 시 탑재할 API Key를 정할 때 게이트웨이는 **"사용자 개별 오버라이드 Key > 시스템 관리자 Key"** 논리를 수행합니다:

1. **개인 오버라이드 Key**: 사용자가 공용 노드에 매핑해 둔 개인용 API Key가 감지되면 해당 Key를 1순위 탑재합니다.
2. **시스템 관리자 Key**: 오버라이드 Key가 비어 있다면 `LLM_AUTO_KEY` 환경 설정 플래그를 체크합니다.

- **`LLM_AUTO_KEY = True`**
  - **⚠️ 과금 유의 조항!**
  - 일반 사용자가 API Key 입력을 생략한 채 공용 플랫폼을 호출하면, 시스템 어드민이 저장해 둔 서버 공용 API Key를 사용해 호출을 성공시킵니다.
  - **장점**: 무료 체험 등 사용자 접근 문턱을 크게 낮출 수 있습니다.
  - **단점**: **서버비 폭탄이 발생할 수 있습니다!** 상용 서비스 운영 시 반드시 구조를 검토하십시오.
- **`LLM_AUTO_KEY = False`**
  - 안전한 보수적 설정입니다.
  - 개인 Key를 기입하지 않은 계정이 모델 호출을 시도하면 즉시 `ValueError` 예외를 트리거하고 입력을 유도합니다.

**운영 셋업 템플릿**:
- **호스팅 비용을 내가 전액 통제할 때**: `LLM_AUTO_KEY = True`로 두고, 요금 차감 성냥(리딤) 정책을 결합해 총 통제권을 쥡니다.
- **비용 소모를 사용자에게 전가할 때**: `LLM_AUTO_KEY = False`로 두고, 사용자가 직접 Key를 입력해 호출하도록 구성합니다.

### 4. 자금 귀속 트랙 분할 및 필터링

과금 정산의 모호함을 걷어내기 위해 모든 호출 이력은 실제 소모된 Key 명의를 대조해 2가지 트랙으로 나뉩니다:

- **`sys_paid`**: 시스템 공용 플랫폼 + 어드민 발급 Key 소모 트랙
- **`self_paid`**: 사용자 고유 Key 소모 트랙
  - 시스템 플랫폼에 기입한 개인 오버라이드 Key 소모분 포함
  - 개인이 커스텀 추가한 사설 플랫폼 소모분 포함

이를 통해 다음이 가능합니다:
- 어드민은 자사 요금이 새 나가는 `sys_paid` 트랙의 한도만 묶어 제한할 수 있습니다.
- 사용자가 일일 무료 `sys_paid` 한도를 다 쓰더라도, 본인 Key로 스위칭하면 `self_paid` 트랙으로 분기되어 즉시 스토리 생성을 이어갈 수 있습니다.
- 서버 마스터 Key가 한도 초과로 마비되더라도 BYOK 사용자들의 정상적인 서비스 작동을 유지합니다.

한도 제약은 `user_quota_policies` 데이터에 개별 기재되며 다음 필터를 걸 수 있습니다:
- **N시간당 슬라이딩 윈도우 한도**: `*_window_hours`, `*_window_token_limit`, `*_window_request_limit`
- **전역 누적 총합 한도**: `*_total_token_limit`, `*_total_request_limit`

### 5. 다용도 타겟팅 슬롯 (Usage Slot)

- **빌트인 슬롯**: 기본적으로 계정마다 `main`, `fast`, `reason` 세 가지 용도 슬롯이 준비되어 있으며 가입 시점에 시스템 디폴트 모델과 매핑됩니다.
- **사용자 슬롯 확장**: API `POST /api/ai/user-selection/usage` 호출 또는 `AIManager.create_user_usage_slot(...)` 호출을 통해 자유로운 명칭의 용도 슬롯을 발급하고 모델을 연결할 수 있습니다.
- **실시간 호출 대응**: `matchbox().get_user_llm(user_id, usage_key="reason")` 호출 시 현재 해당 슬롯에 맵핑된 정확한 모델 인스턴스를 가져와 생성합니다.

## 🚀 빠른 작동 확인

### 1. 패키지 설치
프로젝트 구동에는 `langchain-openai`, `sqlalchemy`, `tiktoken`, `cryptography`, `pyyaml`, `requests` 등의 파이썬 라이브러리가 요구됩니다:

```bash
pip install langchain-core langchain-openai sqlalchemy tiktoken cryptography pyyaml requests python-dotenv
```

### 2. GUI 헬퍼 기동
추천하는 연동 방법입니다. 번잡한 YAML 작성 없이 즉시 데이터베이스를 수정합니다.

```bash
python matchbox_cfg_gui.py
```

> **참고**: YAML 파일 명세는 **최초 부팅** 시에만 증량 전사되며 기존 설정을 침범하지 않습니다. 런타임 신뢰원은 오직 DB 파일입니다.

### 3. 코드 적용 템플릿

```python
from llm.agen_matchbox import initialize_matchbox, matchbox

# 1. 라이프사이클 이니셜라이즈
initialize_matchbox(ensure_defaults=True)

# 2. 인스턴스 획득 및 호출
try:
    user_llm = matchbox().get_user_llm(user_id="user_123")
    response = user_llm.invoke("안녕?")
    print(response.content)
except ValueError as e:
    print(f"연동 에러 발생: {e}")
```

## 📦 데이터베이스 vs YAML 이중 아카이빙

| 데이터원 | 물리 파일 | 반영 템포 | 활용 타깃 |
| --- | --- | --- | --- |
| **데이터베이스** (권장) | `llm_config.db` | 즉시 반영 | 실 서비스 가동, 웹 관리 툴 연동 |
| **YAML 명세** | `matchbox_cfg.yaml` | 서버 재부팅 시 반영 | 최초 빌드 셋업, 설정 아카이빙, 깃 관리 |

### 데이터 전사 조건 (3가지 분기)

1. **최초 이니셜라이즈**: SQLite 파일이 디스크에 존재하지 않는 무상태 시점일 때, YAML 데이터를 통째로 이니셜 로드합니다.
2. **점진 업데이트**: 이미 DB 파일이 존립하는 재기동 시점에는, YAML에 새로 추가된 신규 노드만 읽어와 DB 테이블 아래에 삽입하고 기존 데이터는 훼손하지 않습니다.
3. **강제 초기화**: 어드민 도구나 콘솔 명령을 통해 YAML 데이터로 DB 공용 노드를 리셋 복구할 때 강제 기동합니다. (기존 가입자들의 개인 오버라이드 Key 컬럼은 보존됩니다).

## ⚠️ 마스터 보안 공지
- **⚠️ 1순위 예방 조항**: 실제 운영용 생짜 API Key를 기입한 `matchbox_cfg.yaml` 또는 `.env` 파일을 퍼블릭 Git 저장소에 푸시하는 실수를 절대 저지르지 마십시오.
- **`.gitignore` 설정**: 루트 디렉터리에 `*.env` 필터가 정상 가동하는지 사전에 철저하게 감시하십시오.
- **SQLite 백업**: 사용자 사용량 데이터가 얽힌 `llm_config.db` SQLite 파일은 정기적으로 압축 백업본을 격리 디스크 공간에 분리 보관하는 정책을 지키십시오.

## 📊 디테일 사용량 추적 (Usage Tracking)

`matchbox().get_user_llm()`이 내어주는 `LLMClient`는 사용량 자동 보존 래퍼 클래스입니다:

```python
from llm.agen_matchbox import matchbox

client = matchbox().get_user_llm(user_id="user_123", agent_name="agent_muse")

# 호출 완료 시점 또는 스트리밍 종료 순간, 소모된 정확한 Token 정보가
# SQLite usage_log_entries 테이블 아래에 호출 시퀀스와 성공 값(1/0)을 동시 캡처해 적재됩니다.
result = client.invoke("세계관을 작성해 줘.")

# 24시간 누적량 쿼리
usage_24h = client.usage.get_usage_last_24h()
```

### 토큰 연산 하이브리드 전략 (Token Counter)
1. **Response Usage 우선 채택**: API 반환 패킷 내에 명시된 토큰 사용 객체를 1순위로 채택해 기록합니다.
2. **로컬 토큰 카운터 폴백**: 스트리밍 중도 절단, 혹은 일부 원격 사설 API 명세상 토큰 사용 필드가 완전히 누락되어 오는 경우, `estimate_tokens` 모듈을 가동해 입출력 문자 데이터를 기반으로 토큰을 로컬 역산해 오차 범위를 채워 넣습니다.
3. **생각 크기 합산**: 생각 사슬 필드(`reasoning_content`) 내부에 쌓인 문자 길이도 출력량 카운트에 자동 연계하여 비용 누수가 생기는 현상을 방어합니다.

## 🔄 타 프레임워크로의 어댑팅 (AutoGen / CrewAI 등)

본 컴포넌트는 비즈니스 로직(DB 처리, 암호화, 배정 한도)과 LangChain 인터페이스를 명확하게 디렉터리 분리 설계해 두었습니다:

### 1. AutoGen 적용 시
AutoGen의 `OpenAIChatCompletionClient` 구성 시 resolved 딕셔너리가 뿜어주는 정보들을 대입해 인스턴스화하도록 어댑터를 작성합니다:
```python
from autogen_ext.models.openai import OpenAIChatCompletionClient

resolved = matchbox()._resolve_user_choice(user_id="user_123", usage_key="main")
autogen_client = OpenAIChatCompletionClient(
    model=resolved["model"].model_name,
    api_key=resolved["api_key"],
    base_url=resolved["base_url"]
)
```

### 2. CrewAI 적용 시
CrewAI의 LLM 생성 클래스에 정보를 우회 바인딩합니다:
```python
from crewai import LLM

resolved = matchbox()._resolve_user_choice(user_id="user_123", usage_key="main")
crew_llm = LLM(
    model=f"openai/{resolved['model'].model_name}",
    base_url=resolved["base_url"],
    api_key=resolved["api_key"]
)
```

## 📄 라이선스 조항
본 `server/llm/agen_matchbox` 디렉터리에 기재된 독립 소스코드 번들은 **Apache License 2.0**을 준수합니다. 본 모듈만 따로 떼어내어 다른 AI 상용 어플리케이션의 모델 게이트웨이로 단독 결합 및 개조 사용이 완전 허용됩니다. 

(단, 이는 본 디렉터리에 국한된 Apache 라이선스 승인이며 SparkArc 상위 타 영역의 AGPL-3.0-only 법적 규범은 변경하지 않습니다).
