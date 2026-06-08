# SparkArc 기여 가이드 (한국어)

## 1. 목표 및 포지셔닝
본 가이드는 SparkArc 메인 프로젝트의 강한 제약 조건을 담은 기여 가이드입니다. 프로젝트 규모가 방대하고 멀티 에이전트 협업 아키텍처를 포함하고 있으므로, 모든 기여가(인간 개발자 및 AI 코딩 어시스턴트 포함)는 코드를 작성하거나 수정하기 전에 **반드시 본 가이드를 [AGENTS.md](file:///d:/Desktop/sparkarc/AGENTS.md)와 함께 정독해야 합니다.**
우리는 **"통합 수렴, 중복 구현 배제"**라는 근본 원칙을 따릅니다. 새로운 기능을 개발하기 전, 시스템에 이를 소화할 수 있는 Facade, Pipeline 또는 대통합 인프라가 이미 구현되어 있는지 확인해야 하며, 임의로 평행 파이프라인을 구축하거나 바퀴를 이중으로 발명하는 행위를 엄격히 금지합니다.

## 2. 핵심 아키텍처 및 이중 트랙 파이프라인 협약
SparkArc의 스트리밍 응답 시스템은 책임 경계가 명확히 분리된 두 가지 통로(이중 트랙)로 동작합니다. 두 통로 사이에 이벤트 프로토콜이나 소비기(Consumer)를 혼용해서는 안 됩니다.

### 2.1 채팅 메인 채널 (Chat NDJSON)
- **용도**: 자유로운 대화, 에이전트 위임 스케줄링 상호작용, 도구 호출 시각화.
- **프론트엔드 수렴**: [chatStore.ts](file:///d:/Desktop/sparkarc/client/src/components/stores/chatStore.ts) (`_consumeStream`을 통한 메시지 시간 순서 세그먼트 관리 및 단일 소비).
- **백엔드 수렴**: [chat.py](file:///d:/Desktop/sparkarc/server/agents/routes/chat.py) 라우터 + [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py) (`SparkBaseAgent.chat_stream`).
- **핵심 팩트**:
  - 데이터 전송 포맷은 NDJSON 방식입니다(이벤트는 `task_snapshot`, `assistant_delta`, `reasoning_delta`, `tool_*`, `task_done` 등을 포함).
  - 채팅 상태 및 기록은 Event Log의 점진적 체크포인트(Checkpoint) 모델을 사용해 복구하며, 재연결/화면 새로고침 복구 시 반드시 `task_snapshot` 및 커서 재생을 타야 합니다. **임의로** Progress Queue를 이용한 복구 시도나 파괴적 성격의 `get_nowait` API 호출을 금지합니다.

### 2.2 비즈니스 태스크 채널 (Business SSE / 세맨틱 스트림)
- **용도**: 시간이 오래 걸리는 개별 비즈니스 연산 태스크(예: 문체 클론 스타일 분석, Muse 영감 생성, 설정집 제작, 아웃라인 빌드, 시나리오 실제 집필 등).
- **프론트엔드 수렴**: [streamingRuntime.ts](file:///d:/Desktop/sparkarc/client/src/utils/streamingRuntime.ts) (`createStreamingTask`를 활용해 라이프사이클과 글로벌 딤 처리 통합 관리).
- **백엔드 수렴**: [streaming_utils.py](file:///d:/Desktop/sparkarc/server/agents/routes/streaming_utils.py) (`iterate_sync_iterable_in_thread`를 사용하여 동기식 제너레이터를 스레드 브리지).
- **핵심 팩트**:
  - 표준 의미론적 프레임 규격을 따르며, 일관되게 `onStart` / `onProgress` / `onDelta` / `onStats` / `onDone` / `onError` / `onCancelled` 이벤트 프레임을 내포합니다.
  - 프론트엔드는 개별 컴포넌트 내부에서 임의로 "취소 및 진행 통계" 상태 머신을 각자 만들지 않고, 반드시 `createStreamingTask`를 거치도록 단일화합니다.

## 3. 대통합 도구 및 공통 인프라
프로젝트의 장기 유지보수성을 극대화하고 중복 코드를 제거하기 위해 SparkArc는 다음 공통 유틸리티 인프라를 제공합니다. 아래에 기술된 유틸리티가 필요한 경우 **무조건 하부 구조를 재활용**해야 하며, 개별 에이전트나 비즈니스 영역에서 직접 구현하는 행위를 엄격히 금지합니다:

1. **텍스트 부분 치환 및 점진 패치 (Patch)**:
   - [common.py](file:///d:/Desktop/sparkarc/server/agents/tools/common.py)에 명시된 `_apply_patch` 단일 함수로 수렴합니다. 극본 리라이팅, 아웃라인 부분 치환, 설정 카드 업데이트 등 파일 텍스트 수정 시 반드시 이 함수를 타야 하며, 정규식이나 `.replace()`를 개별 구현하지 마십시오.
2. **토큰 단위 텍스트 쪼개기 (Token Chunking)**:
   - [chunking.py](file:///d:/Desktop/sparkarc/server/core/file_ingest/chunking.py)의 `TokenTextSplitter` 클래스로 통합합니다. 토큰 크기 한도에 맞춘 문자열 슬라이싱이 필요한 연산에 일괄 활용됩니다.
3. **세맨틱 의미론적 분할기 (Semantic Chunker)**:
   - [SemanticChunker](file:///d:/Desktop/sparkarc/server/story/semantic_chunker/) 폴더로 수렴합니다. 벡터 임베딩, 지식 그래프 RAG 연산을 위한 단락 자르기 시 이를 통과해야 합니다.
4. **인프라 확장 기준**:
   - 향후 다수 컴포넌트가 혼용할 여지가 있는 핵심 인프라(벡터 색인, 캐시 튜닝, 파일 분석 등)를 제작할 때는 비즈니스단에 기재하지 말고 우선적으로 공통 도구 레이어나 코어 서비스 층에 하강하여 작성해 주십시오.

## 4. 백엔드 확장 및 에이전트 3개 기동 모드 계약
새로운 에이전트나 도구(Tool)를 등록할 때는 아래 절차를 성실히 이행해야 합니다:

### 4.1 신규 에이전트 등록 프로시저
1. **공통 베이스 상속**: 특수 예외 상황을 제외하고 `SparkBaseAgent`(통신 및 대화 담당)와 `SparkAgentExecutor`(실행 생명주기 관리)를 의무 상속받아 개발합니다.
2. **4대 등록 지점**:
   - [registry.py](file:///d:/Desktop/sparkarc/server/agents/registry.py): 에이전트 기본 프로필 메타데이터를 기입합니다.
   - [runtime.py](file:///d:/Desktop/sparkarc/server/agents/routes/runtime.py): 라우터 결합 및 락(Lock) 정책 설정 시 사용합니다.
   - [agent_tools.py](file:///d:/Desktop/sparkarc/server/agents/agent_tools.py) 및 [tools/registry.py](file:///d:/Desktop/sparkarc/server/agents/tools/registry.py): 신규 제작한 도구를 등록하고 해당 에이전트와 바인딩합니다.
   - [director_graph.py](file:///d:/Desktop/sparkarc/server/agents/director_graph.py): 감독 에이전트의 위임 대상 리스트에 편입시킬지 여부를 기재합니다.

### 4.2 에이전트 3지점 지침 조약
모든 전문가 에이전트는 거동 시나리오에 얽히지 않도록 아래 3가지 YAML 지침 속성을 독립적으로 충족해야 합니다:
- **전용 연산 태스크 모드 (Specialized Work)**: `agent.execute()`로 직접 시작됩니다. YAML의 `system` 및 `user` 지침을 탑재합니다. 데이터 출력이 파서 규격을 엄격히 통과해야 하므로 불필요한 친근한 꼬리말이나 설명은 작성하지 않습니다.
- **사용자 대면 모드 (Chat Mode)**: 일반 채팅 채널에서 가동됩니다. YAML의 `chat_system` 지침을 타며, 편안한 대화와 제안을 수행합니다.
- **감독 지시 수임 모드 (Pipeline Mode)**: 감독 에이전트가 가동합니다. YAML의 `pipeline_system` 지침을 타며, 감독 에이전트를 향한 보고 및 도구 호출 결과 요약 규격에 맞춥니다.

#### 프롬프트 설계 유일 진실 공급원 (Single Source of Truth)
1. **도구 준수사항 자동 주입 (Tool Reference)**:
   - `_get_tool_prompt_references()`를 선언해 규격 준수사항을 도구의 YAML `system` 단락에 묶어놓습니다. `pipeline_system` 지침 파일은 수령자 선언과 지시 요약으로 최소화해야 하며, 포맷 규칙을 `pipeline_system` 내부에 똑같이 카피해 붙여넣지 마십시오.
2. **베이직 셰어 단락 (`base` 필드)**:
   - 중복되는 역할 페르소나는 YAML의 `base` 단락에 빼두고, 호출 시 `{base.xxx}` 치환기를 활용해 템플릿화합니다.
3. **도구 전용 매개 제약 (`tool_rules` 필드)**:
   - 에이전트 전용의 도구 순서, 예외 필터 규칙 등은 YAML의 `tool_rules` 필드에 기재하며, 파이썬 파일 내에 로직을 문자열로 하드코딩해서는 안 됩니다.

## 5. 프론트엔드 확장 및 다국어 지원 (I18n)
1. **도구와 UI 상태 싱크로율**:
   - 도구 실행에 따른 UI 변경 파라미터(`ui_scope` / `ui_target` / `ui_refresh_events`)는 백엔드 [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py)의 `build_tool_stream_event` 함수에서 캡슐화해 내려보내며, 프론트엔드는 `chatStore`에서 받아 실행해야 합니다. 프론트엔드에 트리거 이벤트를 하드코딩하지 마십시오.
2. **프론트엔드 추가 반영 체크리스트**:
   - 에이전트를 가감할 시 다음 파일들의 정보 일치 여부를 파악하십시오:
     1. 기본 타겟팅: [GlobalChatFloat.vue](file:///d:/Desktop/sparkarc/client/src/components/share/GlobalChatFloat.vue) (`viewAgentMap`).
     2. 채팅 말풍선 데코: [useAgentRegistry.ts](file:///d:/Desktop/sparkarc/client/src/composables/useAgentRegistry.ts) (`agentIconMap`, `agentColorMap`, `agentNameMap`).
     3. 캔버스 노드: [AgentFlowBlueprint.vue](file:///d:/Desktop/sparkarc/client/src/components/lorebook/AgentFlowBlueprint.vue).
     4. 모의 데이터: `agentRuntimeStore.ts`.
     5. 세팅 창: `AiSettingsPanel.vue`.
3. **다국어 (Vue I18n) 엄격 준수**:
   - 사용자용 텍스트를 소스 코드에 **날것으로 기재하는 것을 엄격히 금지**합니다. 노출되는 텍스트는 `zh-CN`, `en-US`, `ja-JP`, `ko-KR` 리소스에 균등 반영되어야 합니다.

## 6. 스키마 보존 및 마이그레이션 정책
1. **Alembic 파일 직접 개작 및 수동 제작 절대 금지**:
   - 데이터베이스 스키마 형태를 변경할 때는 오직 [models.py](file:///d:/Desktop/sparkarc/server/core/models.py)의 클래스 정의만 수정한 후 아래 마이그레이션 자동 변환 명령을 통해 파일을 획득해야 합니다:
     `python server/gen_migration.py`
     시스템 기동 시 자동으로 [auto_migrate.py](file:///d:/Desktop/sparkarc/server/core/auto_migrate.py) 파일이 기동되어 서버의 DB 상태를 안전하게 밀어 올립니다.

## 7. 최악의 안티 패턴 (경고 조항)
SparkArc 기여 도중 아래에 기술된 구현을 적용할 시 **심각한 아키텍처 위반**으로 규정합니다:
1. **라우터 내 중복 브리지**: `streaming_utils.py`를 거치지 않고 개별 라우터 함수 내부에서 스레드 대기 스트리밍 연산을 각자 작성하는 행위.
2. **딤 처리 수동 조작**: `createStreamingTask`를 우회하고 프론트엔드 컴포넌트 생명주기 훅에서 로딩 마스크 상태 변수를 수동 스위칭하는 행위.
3. **양측 정보 불일치**: 백엔드 `build_tool_stream_event`를 우회하여 프론트엔드 단에서 독자적인 도구 연동 콜백 상태기를 하드코딩 구현하는 행위.
4. **프로토콜 가공 혼용**: NDJSON 채팅 패킷을 SSE 태스크 채널에 억지로 집어넣거나, SSE 비즈니스 패킷을 `chatStore`로 흘려보내는 거동.
5. **에이전트 단 독자 디렉터리 IO**: `write_result` 공통 처리 파이프라인을 패스하고 에이전트 클래스 내부에서 디스크 물리 경로를 생성해 파일 IO를 행하는 행위.
6. **유령 구성**: 에이전트나 도구를 만들고 `registry.py` 설정 파일 갱신을 생략하는 방치 행위.
7. **스키마 불법 수정**: `gen_migration.py`를 타지 않고 운영 서버 DB 파일에 직접 수동으로 SQL DDL을 밀어 넣는 행위.
8. **Git 원격 오염**: 테스트 코드를 가동하면서 획득한 벡터 캐시 번들, 임베딩 DB, 시리얼 임시 파일 등을 Git 추적 하부 테스트 디렉터리(`server/test/` 등)에 그대로 커밋하여 저장소를 지저분하게 오염시키는 행위.
9. **역방향 참조 순환**: 최하부 공통 인프라 코드나 유틸리티 파일에서 라우터 레이어(`server/agents/routes/*`) 소스코드를 임포트해 사용하는 순환 모듈 종속성 야기.
10. **뮤텍스 부재**: 오래 걸리는 물리적 파일 쓰기 태스크에 락(Lock)을 걸지 않거나, 프론트엔드가 재시도 요청을 날릴 때 고유 식별값 `clientId`를 공백으로 누락하는 행동.

## 8. 회귀 테스트 및 임시 산출물 격리선
채팅 패킷, 멀티 에이전트 동선 조율 코드를 손봤을 때는 반드시 아래 명기된 검증을 돌려 성공해야 하며, 임시 파일 잔여 수칙을 준수해야 합니다:

### 8.1 임시 파일 수납 격리선 (필수 준수)
- 검증 테스트 기동, 임시 확인 로직 실행 도중 발생한 모든 캐시 파일, 색인DB, 마크업 파일은 **무조건 프로젝트 루트 디렉터리 하부의 `/.tmp/` 폴더 내에 수납해야 합니다.**
- `server/test/` 및 그 하위 폴더에 임시 부산물을 흘려두는 행위를 일절 금지하여 Git 기록을 엄격히 방어합니다.

### 8.2 리그레션 회귀 테스트 명령 셋
- **백엔드 테스트**:
  ```bash
  cd server
  pytest test/test_chat_stream_events.py test/test_chat_history_segments.py test/test_tool_event_ui_metadata.py test/test_director_graph.py test/test_director_handoff_protocol.py test/test_director_skip_confirmation.py test/test_stream_semantics_runtime.py
  ```
- **프론트엔드 테스트**:
  ```bash
  cd client
  npm run test -- src/components/stores/__tests__/chatStore.spec.ts src/utils/__tests__/streamingRuntime.spec.ts
  ```

## 9. AI 권한 제한 및 안전 수칙
1. 사용자가 명확히 **简体中文 (간체중문)** 단어로 쓰기 권한 명령을 내린 특수 상황을 빼고는, AI 코딩 어시스턴트는 오직 【읽기 전용】 Git 명령만 수행 가능하며 `git commit`, `git push` 등 상태 변경 명령을 기동할 수 없습니다.
2. 시스템이 자동 승인(Auto-Approve) 상태라 하더라도 어시스턴트는 방어적으로 움직여야 하며, 이를 사용자 본인의 최종 의도로 넘겨짚어 GitHub CLI 등을 통해 원격 저장소를 조작해서는 절대 안 됩니다.
