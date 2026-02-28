# CLAUDE.md — kuksa-mcp-bridge

## 🚨 QUALITY RULES (READ FIRST, NEVER SKIP)

### Anti-Degradation Policy
이 프로젝트는 포트폴리오용입니다. "일단 동작하면 됨" 수준이 아니라 **면접관이 코드를 열어봐도 감탄할 수준**이어야 합니다.

**절대 하지 말 것:**
- `# TODO: implement later` 남기고 넘어가기
- 에러 핸들링 없이 `pass`나 빈 `except`로 넘기기
- 하드코딩된 값 (매직 넘버, 하드코딩 경로)
- `print()` 디버깅을 로깅 대신 사용
- 테스트 없이 "동작할 것 같다"며 넘어가기
- 타입 힌트 생략
- docstring 생략
- 한 함수에 50줄 이상 작성

**반드시 할 것:**
- 모든 함수에 타입 힌트 + docstring
- `logging` 모듈 사용 (print 금지)
- 에러는 구체적 예외로 catch + 의미 있는 메시지
- 환경 변수 또는 config 파일로 설정 관리
- 각 모듈마다 최소 기본 테스트 존재

### Definition of Done (모든 작업에 적용)
작업이 "완료"되었다고 판단하려면 다음을 모두 충족해야 합니다:
1. ✅ 코드가 에러 없이 실행됨
2. ✅ 타입 힌트 100% 적용
3. ✅ docstring 있음 (함수, 클래스, 모듈)
4. ✅ 테스트가 존재하고 통과함
5. ✅ `docker compose up`으로 전체 시스템 실행 가능
6. ✅ README 또는 해당 문서가 최신 상태

---

## 📋 Project Overview

### One-Line Summary
Eclipse Kuksa Databroker(VSS)의 차량 데이터를 AI가 자연어로 조회·제어·진단할 수 있도록 MCP 프로토콜로 연결하는 브릿지 서버 + IVI 대시보드.

### Why This Exists
- COVESA VSS: 자동차 업계 표준 데이터 모델 (4,000+ 시그널)
- Eclipse Kuksa: VSS를 구현한 gRPC 서버 (Apache 2.0)
- MCP: AI-도구 연결 표준 (MIT)
- **Gap: VSS/Kuksa ↔ MCP 브릿지가 세계적으로 존재하지 않음**

### Architecture (5 Layers)
```
┌─────────────────────────────────────────────────┐
│  ⑤ React IVI Dashboard                          │
│     (차량 상태 시각화 + AI 채팅 패널)             │
├─────────────────────────────────────────────────┤
│  ④ kuksa-mcp-bridge  ★ 핵심 (직접 구현)         │
│     (Kuksa gRPC → MCP Tools/Resources 변환)      │
├─────────────────────────────────────────────────┤
│  ③ Kuksa Databroker (Docker, 기존 오픈소스)       │
│     (VSS 트리 관리 + gRPC API)                   │
├─────────────────────────────────────────────────┤
│  ② Kuksa CAN Provider + DBC (차종 확장용)        │
│     (DBC 파일 → vcan → VSS 변환)                │
├─────────────────────────────────────────────────┤
│  ① Python Vehicle Simulator (시나리오 제어용)     │
│     (RPM, 속도, 온도, DTC 등 ~30개 시그널 생성)   │
└─────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
kuksa-mcp-bridge/
├── CLAUDE.md                    # 이 파일
├── README.md                    # 프로젝트 소개 + 아키텍처 다이어그램
├── docker-compose.yml           # 원클릭 실행
├── .env.example                 # 환경 변수 템플릿
│
├── mcp-server/                  # ★ 핵심: MCP 브릿지 서버
│   ├── pyproject.toml
│   ├── src/
│   │   └── kuksa_mcp/
│   │       ├── __init__.py
│   │       ├── server.py        # FastMCP 서버 메인 엔트리
│   │       ├── tools.py         # MCP Tools 정의
│   │       ├── resources.py     # MCP Resources 정의
│   │       ├── prompts.py       # MCP Prompts 정의
│   │       ├── kuksa_client.py  # Kuksa Databroker gRPC 래퍼
│   │       ├── dtc_database.py  # DTC 코드 → 설명 매핑
│   │       └── config.py        # 설정 관리
│   └── tests/
│       ├── test_tools.py
│       ├── test_resources.py
│       └── test_kuksa_client.py
│
├── simulator/                   # 가상 차량 데이터 생성기
│   ├── pyproject.toml
│   ├── src/
│   │   └── vehicle_sim/
│   │       ├── __init__.py
│   │       ├── main.py          # 시뮬레이터 메인 루프
│   │       ├── engine.py        # 엔진 시그널 (RPM, 온도, 부하)
│   │       ├── vehicle.py       # 주행 시그널 (속도, 주행거리)
│   │       ├── hvac.py          # HVAC 시그널 (실내온도, 설정온도)
│   │       ├── battery.py       # 배터리 시그널 (SOC, 전압, 온도)
│   │       ├── dtc.py           # DTC 발생 시뮬레이션
│   │       └── scenarios.py     # 사전 정의 시나리오 (정상주행, 고장 등)
│   └── tests/
│
├── dashboard/                   # React IVI 대시보드
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Speedometer.tsx   # 원형 속도계 게이지
│   │   │   ├── RpmGauge.tsx      # RPM 미터
│   │   │   ├── HvacPanel.tsx     # HVAC 제어 패널
│   │   │   ├── BatteryStatus.tsx # 배터리 상태
│   │   │   ├── DtcWarning.tsx    # DTC 경고 카드
│   │   │   └── AiChatPanel.tsx   # AI 채팅 인터페이스
│   │   ├── hooks/
│   │   │   └── useKuksaWebSocket.ts  # Kuksa WebSocket 연결
│   │   └── types/
│   │       └── vss.ts            # VSS 시그널 타입 정의
│   └── tests/
│
├── dbc/                         # DBC 파일 및 매핑
│   ├── hyundai_ioniq.dbc        # 현대 아이오닉 (opendbc 소스)
│   ├── tesla_model3.dbc         # 테슬라 M3 (Kuksa 내장)
│   └── mappings/
│       ├── hyundai_vss_dbc.json # 현대 DBC → VSS 매핑
│       └── tesla_vss_dbc.json   # 테슬라 DBC → VSS 매핑
│
└── docs/
    ├── architecture.md          # 상세 아키텍처 문서
    ├── mcp-design.md            # MCP Tool/Resource/Prompt 설계 근거
    └── demo-scenarios.md        # 데모 시나리오 스크립트
```

---

## 🔧 Tech Stack

| 영역 | 기술 | 버전 기준 |
|------|------|----------|
| MCP 서버 | Python + FastMCP (mcp SDK) | latest |
| Kuksa 연결 | kuksa-client (Python gRPC) | latest |
| 데이터 저장소 | Kuksa Databroker (Docker) | latest |
| CAN Provider | eclipse-kuksa/kuksa-can-provider | latest |
| DBC 소스 | commaai/opendbc (MIT) | latest |
| 프론트엔드 | React 18 + TypeScript + Tailwind CSS | React 18 |
| 차트/게이지 | Recharts 또는 D3.js | - |
| 실시간 통신 | WebSocket (Kuksa VISS v2) | - |
| 에이전트 | LangGraph 또는 ReAct 패턴 | - |
| 컨테이너 | Docker Compose | v2 |
| 테스트 | pytest (Python), vitest (React) | - |

---

## 🎯 Implementation Phases

### Phase 1: MCP 브릿지 핵심 구현 (Weeks 1-2)

**목표:** Claude Desktop에서 "차량 속도 알려줘"라고 물으면 Kuksa에서 값을 가져와서 응답하는 것.

#### Phase 1-A: 인프라 + Custom Simulator

**Task 1.1: Docker Compose 기본 세팅**
- Kuksa Databroker 컨테이너
- VSS metadata 로딩 확인
- 헬스체크 설정
- ✅ 완료 기준: `docker compose up` → `grpcurl`로 Kuksa 응답 확인

**Task 1.2: Python Vehicle Simulator**
- kuksa-client로 Databroker에 값 주입
- 시그널 목록 (최소):
  - `Vehicle.Speed` (0~200 km/h)
  - `Vehicle.Powertrain.TractionBattery.StateOfCharge.Current` (0~100%)
  - `Vehicle.Powertrain.CombustionEngine.Speed` (0~8000 rpm)
  - `Vehicle.Powertrain.CombustionEngine.ECT` (엔진 냉각수 온도)
  - `Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature` (설정 온도)
  - `Vehicle.Cabin.HVAC.AmbientAirTemperature` (실내 온도)
  - `Vehicle.OBD.DTCList` (DTC 코드 목록)
- 시나리오 모드: normal_driving, engine_warning, battery_low
- ✅ 완료 기준: Simulator 실행 → `databroker-cli`로 값 변화 확인

**Task 1.3: kuksa-mcp-bridge 서버 구현**

MCP Tools (6개):
```python
@mcp.tool()
async def get_vehicle_signal(path: str) -> dict:
    """단일 VSS 시그널 조회. 예: Vehicle.Speed"""

@mcp.tool()
async def get_multiple_signals(paths: list[str]) -> dict:
    """여러 VSS 시그널 동시 조회"""

@mcp.tool()
async def set_actuator(path: str, value: float | str | bool) -> dict:
    """차량 액추에이터 제어. 예: HVAC 온도 설정"""

@mcp.tool()
async def diagnose_dtc() -> dict:
    """현재 DTC 코드 조회 + 자연어 설명 반환"""

@mcp.tool()
async def search_vss_tree(keyword: str) -> dict:
    """VSS 카탈로그에서 키워드로 시그널 검색"""

@mcp.tool()
async def subscribe_signals(paths: list[str], duration_seconds: int = 10) -> dict:
    """시그널 변화를 일정 시간 구독하여 트렌드 반환"""
```

MCP Resources (3개):
```python
@mcp.resource("vss://tree")
async def get_vss_tree() -> str:
    """VSS 트리 전체 구조 (AI가 어떤 시그널이 있는지 파악용)"""

@mcp.resource("vss://metadata/{path}")
async def get_signal_metadata(path: str) -> str:
    """특정 시그널의 메타데이터 (단위, 타입, 설명)"""

@mcp.resource("vss://dtc-database")
async def get_dtc_database() -> str:
    """DTC 코드 → 자연어 설명 매핑 데이터베이스"""
```

MCP Prompts (3개):
```python
@mcp.prompt()
def vehicle_health_check() -> str:
    """차량 전반 건강 상태 점검 프롬프트"""

@mcp.prompt()
def driving_analysis() -> str:
    """최근 주행 패턴 분석 + 연비 개선 팁 프롬프트"""

@mcp.prompt()
def diagnose_symptom(symptom: str) -> str:
    """증상 기반 진단 프롬프트"""
```

- ✅ 완료 기준: MCP Inspector에서 6개 Tool, 3개 Resource, 3개 Prompt 모두 정상 동작
- ✅ 완료 기준: Claude Desktop에 연결하여 "차량 속도 알려줘" → 실제 값 응답

**Task 1.4: 테스트**
- kuksa_client.py 단위 테스트 (mock gRPC)
- tools.py 통합 테스트 (실제 Databroker 연결)
- ✅ 완료 기준: `pytest` 전체 통과

#### Phase 1-B: DBC Feeder 통합 (확장성 증명)

**Task 1.5: CAN Provider 설정**
- kuksa-can-provider Docker 컨테이너 추가
- opendbc에서 현대 아이오닉 DBC 파일 획득
- vss_dbc.json 매핑 파일 작성
- vcan0 가상 CAN 인터페이스 설정
- ✅ 완료 기준: DBC → CAN Provider → Databroker로 시그널 흐름 확인

**Task 1.6: 차종 전환 테스트**
- DBC 파일만 교체해서 현대 → 테슬라 전환
- MCP 서버 코드 수정 없이 동작 확인
- ✅ 완료 기준: DBC 교체 전후 동일 MCP 쿼리 성공

---

### Phase 2: IVI 대시보드 UI (Week 3)

**목표:** 브라우저에서 실시간으로 차량 상태를 볼 수 있는 대시보드.

**Task 2.1: React 프로젝트 세팅**
- Vite + React 18 + TypeScript + Tailwind CSS
- ✅ 완료 기준: `npm run dev` → 빈 페이지 렌더링

**Task 2.2: 차량 상태 컴포넌트 (좌측 패널)**
- Speedometer: 원형 게이지, 0~200 km/h
- RpmGauge: 바 게이지 또는 원형, 0~8000 rpm
- HvacPanel: 현재 온도 표시 + 설정 온도 슬라이더 (조작 가능)
- BatteryStatus: SOC %, 전압, 온도
- DtcWarning: DTC 발생 시 빨간색 경고 카드 (코드 + 설명)
- ✅ 완료 기준: 각 컴포넌트가 props로 받은 값을 정상 렌더링

**Task 2.3: WebSocket 실시간 연결**
- useKuksaWebSocket 커스텀 훅
- Kuksa Databroker의 VISS v2 WebSocket 엔드포인트에 연결
- 시그널 구독 → state 업데이트 → 컴포넌트 자동 리렌더
- 연결 끊김 시 자동 재연결 (exponential backoff)
- ✅ 완료 기준: Simulator 값 변경 → 대시보드에 1초 이내 반영

**Task 2.4: 레이아웃 통합**
- 좌측 60%: 차량 상태 패널
- 우측 40%: AI 채팅 패널 (Phase 3에서 구현, 여기선 빈 영역)
- 반응형 디자인 (최소 1280x720)
- ✅ 완료 기준: 전체 대시보드가 한 화면에 깔끔하게 렌더링

---

### Phase 3: AI 채팅 + 에이전트 파이프라인 (Week 4)

**목표:** 대시보드 안에서 AI와 대화하며 차량을 제어/진단하는 경험.

**Task 3.1: AI 채팅 패널 UI**
- 채팅 입력/출력 인터페이스
- 메시지 버블 (사용자 / AI)
- 진단 결과 카드 UI
- 로딩 상태 표시
- ✅ 완료 기준: 텍스트 입출력 동작

**Task 3.2: 멀티 MCP 서버 오케스트레이션**
- kuksa-mcp-bridge (직접 구현) — 차량 데이터/제어/진단
- Web Search MCP (기존) — DTC 원인/수리 비용 검색
- 에이전트가 상황에 따라 어떤 MCP 서버를 호출할지 자율 판단
- ✅ 완료 기준: "엔진 경고등이 켜졌는데 이상한 소리가 나요" → 자동으로 diagnose_dtc + web_search 호출

**Task 3.3: 엔진 진단 end-to-end 시나리오**
데모 시나리오:
1. 사용자: "엔진 경고등이 켜졌고 이상한 소리가 나요"
2. AI → diagnose_dtc() → P0301 (실린더 1 미스파이어)
3. AI → get_multiple_signals() → RPM 변동, 엔진 온도, 연료 분사량
4. AI → web_search("P0301 misfire 수리 비용")
5. AI → 종합 진단 보고서 생성
- ✅ 완료 기준: 위 시나리오가 end-to-end로 동작

**Task 3.4: AI → 대시보드 실시간 반영**
- AI가 set_actuator("HVAC 24도")를 호출하면
- Kuksa Databroker의 값이 바뀌고
- WebSocket으로 대시보드의 HVAC 패널이 실시간 업데이트
- ✅ 완료 기준: AI 명령 → 대시보드 반영 2초 이내

---

### Phase 4: 폴리싱 + 포트폴리오 패키징 (Week 5)

**Task 4.1: README.md**
- 프로젝트 한 줄 설명
- 아키텍처 다이어그램 (Mermaid 또는 이미지)
- Quick Start (`docker compose up`)
- 데모 GIF/영상 링크
- MCP Tool/Resource/Prompt 목록
- 기술 스택
- ✅ 완료 기준: README만 보고 3분 내 프로젝트 이해 가능

**Task 4.2: Docker Compose 최종 검증**
- 서비스: databroker, can-provider, simulator, mcp-server, dashboard
- `docker compose up` → 모든 서비스 healthy
- `docker compose down` → 깔끔한 정리
- ✅ 완료 기준: 클론 후 docker compose up만으로 전체 데모 가능

**Task 4.3: 데모 모드 전환**
- Mode 1 (기본): Custom Simulator → DTC 진단 시나리오
- Mode 2 (차종 확장): DBC 파일 교체 → 현대↔테슬라 전환
- Mode 3 (실차): Tesla M3 CAN dump replay
- ✅ 완료 기준: Mode 전환 시 MCP 서버 코드 수정 0줄

---

## 🏗️ Code Conventions

### Python (mcp-server, simulator)
```python
# 파일 상단에 항상 모듈 docstring
"""Vehicle signal tools for MCP server.

Provides MCP tools that bridge Kuksa Databroker gRPC API
to the Model Context Protocol.
"""

# 함수는 반드시 타입 힌트 + docstring
async def get_vehicle_signal(path: str) -> dict[str, Any]:
    """Query a single VSS signal from Kuksa Databroker.

    Args:
        path: VSS signal path (e.g., "Vehicle.Speed")

    Returns:
        dict with keys: path, value, timestamp, unit

    Raises:
        SignalNotFoundError: If the VSS path doesn't exist
        ConnectionError: If Databroker is unreachable
    """

# 로깅
import logging
logger = logging.getLogger(__name__)
logger.info("Querying signal: %s", path)  # f-string 아닌 % 포맷 사용

# 설정은 환경 변수 또는 config
KUKSA_HOST = os.getenv("KUKSA_DATABROKER_HOST", "localhost")
KUKSA_PORT = int(os.getenv("KUKSA_DATABROKER_PORT", "55555"))
```

### TypeScript (dashboard)
```typescript
// 컴포넌트는 항상 Props 인터페이스 정의
interface SpeedometerProps {
  speed: number;          // km/h, 0~200
  maxSpeed?: number;      // 게이지 최대값 (default: 200)
  warningThreshold?: number; // 경고 색상 임계값
}

// 컴포넌트 export
export const Speedometer: React.FC<SpeedometerProps> = ({
  speed,
  maxSpeed = 200,
  warningThreshold = 160,
}) => {
  // ...
};

// 커스텀 훅은 use 접두어
export function useKuksaWebSocket(signals: string[]): VssSignalState {
  // ...
}
```

---

## ⚠️ Common Pitfalls (Claude Code가 빠지기 쉬운 함정)

### 1. Kuksa 연결 실패 무시
```python
# ❌ BAD: 에러 삼켜버리기
try:
    value = await kuksa.get(path)
except Exception:
    return None

# ✅ GOOD: 구체적 에러 처리
try:
    value = await kuksa.get(path)
except grpc.RpcError as e:
    if e.code() == grpc.StatusCode.NOT_FOUND:
        raise SignalNotFoundError(f"VSS path not found: {path}") from e
    raise ConnectionError(f"Databroker unreachable: {e.details()}") from e
```

### 2. MCP Tool 응답 구조 불일치
```python
# ❌ BAD: 매번 다른 형태의 응답
return {"speed": 120}           # 어떤 tool
return {"value": 120, "unit": "km/h"}  # 다른 tool

# ✅ GOOD: 일관된 응답 구조
return {
    "path": "Vehicle.Speed",
    "value": 120.0,
    "unit": "km/h",
    "timestamp": "2025-07-15T10:30:00Z",
    "status": "ok"
}
```

### 3. Docker Compose에서 서비스 순서 무시
```yaml
# ✅ GOOD: depends_on + healthcheck
services:
  databroker:
    healthcheck:
      test: ["CMD", "grpc_health_probe", "-addr=:55555"]
      interval: 5s
      timeout: 3s
      retries: 5

  mcp-server:
    depends_on:
      databroker:
        condition: service_healthy
```

### 4. 대시보드 WebSocket 재연결 미구현
```typescript
// ✅ GOOD: 반드시 재연결 로직 포함
useEffect(() => {
  let ws: WebSocket;
  let reconnectTimeout: number;

  const connect = () => {
    ws = new WebSocket(wsUrl);
    ws.onclose = () => {
      reconnectTimeout = setTimeout(connect, 3000);
    };
  };

  connect();
  return () => {
    clearTimeout(reconnectTimeout);
    ws?.close();
  };
}, [wsUrl]);
```

---

## 🧪 Testing Strategy

### Python
```bash
# 단위 테스트 (mock Kuksa)
pytest mcp-server/tests/ -v

# 통합 테스트 (실제 Databroker 필요)
docker compose up databroker -d
pytest mcp-server/tests/ -v -m integration
```

### React
```bash
cd dashboard
npm run test        # vitest
npm run lint        # eslint
npm run typecheck   # tsc --noEmit
```

### End-to-End
```bash
docker compose up -d
# 1. Simulator가 데이터 생성 중인지 확인
docker compose logs simulator | grep "Publishing"

# 2. MCP Inspector로 tool 호출
npx @modelcontextprotocol/inspector

# 3. 대시보드 접속
open http://localhost:5173
```

---

## 📦 Key Dependencies

### Python
```
mcp                    # MCP SDK (FastMCP)
kuksa-client           # Eclipse Kuksa Python SDK
grpcio                 # gRPC for Python
pydantic               # Data validation
python-dotenv          # .env 파일 로딩
pytest                 # 테스트
pytest-asyncio         # 비동기 테스트
```

### Node.js
```
react, react-dom       # UI
typescript             # 타입 안전성
tailwindcss            # 스타일링
recharts               # 차트/게이지
vite                   # 빌드 도구
vitest                 # 테스트
```

---

## 🚀 Quick Reference Commands

```bash
# 전체 시스템 실행
docker compose up -d

# 전체 시스템 중지
docker compose down

# MCP 서버만 개발 모드
cd mcp-server && uv run python -m kuksa_mcp.server

# 시뮬레이터만 실행
cd simulator && uv run python -m vehicle_sim.main

# 대시보드 개발 모드
cd dashboard && npm run dev

# 테스트
cd mcp-server && uv run pytest -v
cd dashboard && npm run test
```

---

## 🔑 Environment Variables

```env
# Kuksa Databroker
KUKSA_DATABROKER_HOST=localhost
KUKSA_DATABROKER_PORT=55555

# Simulator
SIM_MODE=normal_driving          # normal_driving | engine_warning | battery_low
SIM_UPDATE_INTERVAL_MS=500       # 시그널 업데이트 주기

# MCP Server
MCP_SERVER_NAME=kuksa-vehicle-bridge
MCP_LOG_LEVEL=INFO

# Dashboard
VITE_KUKSA_WS_URL=ws://localhost:8090
VITE_AI_API_URL=http://localhost:8080
```

---

## 📌 Phase Checklist (진행 상황 추적)

### Phase 1-A
- [x] Docker Compose + Databroker 실행
- [x] Vehicle Simulator 구현 (6개 시그널 그룹)
- [x] MCP Tools 6개 구현
- [x] MCP Resources 3개 구현
- [x] MCP Prompts 3개 구현
- [x] MCP Inspector 테스트 통과
- [x] Claude Desktop 연결 테스트

### Phase 1-B
- [x] CAN Provider Docker 추가
- [x] opendbc DBC 파일 획득 + 매핑
- [x] vcan0 설정
- [x] DBC 교체로 차종 전환 증명

### Phase 2
- [x] React 프로젝트 세팅
- [x] Speedometer 컴포넌트
- [x] RpmGauge 컴포넌트
- [x] HvacPanel 컴포넌트 (조작 가능)
- [x] BatteryStatus 컴포넌트
- [x] DtcWarning 컴포넌트
- [x] WebSocket 실시간 연결
- [x] 전체 레이아웃 통합

### Phase 3
- [x] AI 채팅 패널 UI
- [x] 멀티 MCP 오케스트레이션
- [x] 엔진 진단 E2E 시나리오
- [x] AI → 대시보드 실시간 반영

### Phase 4
- [x] README.md (portfolio-grade, Mermaid 아키텍처, 배지, 스크린샷)
- [x] .gitignore (Python + Node + Docker + .env 보호)
- [x] Docker Compose 최종 검증 (healthcheck, clean up/down)
- [x] 스크린샷 정리 (docs/images/로 이동)
- [x] docs/architecture.md (5계층 데이터 흐름, 컴포넌트 상세, 포트 매핑)
- [x] docs/mcp-design.md (6 Tools, 3 Resources, 3 Prompts 설계 근거)
- [x] docs/demo-scenarios.md (면접 데모 시나리오 대사 포함)
- [x] scripts/demo.sh (Mode 1/2/3 전환 스크립트)
- [x] 코드 품질 정리 (중복 파일 삭제, 테스트 통과 확인)
- [ ] 데모 영상 녹화