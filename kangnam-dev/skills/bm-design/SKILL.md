---
name: bm-design
description: "Business model design — revenue structures, pricing strategies, unit economics. Triggers on monetization, pricing, or revenue model requests."
---

# BM Designer

제품/서비스의 비즈니스 모델을 설계하는 오케스트레이션 워크플로우. 이 스킬은 컨텍스트 수집, 시장 조사, 전략 검증, 문서 생성을 오케스트레이션하고, 핵심 BM 설계 로직(수익 모델 선택, 유닛 이코노믹스, BM Score)은 **bm-designer helper**에게 위임한다.

## 모드

| 모드 | 진입 조건 | 시작 Phase |
|------|----------|-----------|
| **독립 실행** | 사용자가 직접 호출, 외부 컨텍스트 없음 | Phase 1 |
| **파이프라인 모드** | 상위 워크플로우(idea-forge, auto-dev)가 외부 컨텍스트 주입 | Phase 1 스킵 → Phase 2 (리서치 데이터 있으면 축약) |

## 워크플로우

```
[진입 분기]
  ├─ 외부 컨텍스트 없음 → Phase 1부터
  └─ 외부 컨텍스트 있음 → Phase 1 스킵
        ├─ 리서치 데이터 포함 → Phase 2 축약 (갭 분석만)
        └─ 리서치 데이터 없음 → Phase 2 전체

Phase 1: 컨텍스트 수집 (이 스킬이 직접 수행)
    ↓
Phase 2: 시장 조사 (bm-researcher helper 호출, skill-local)
    ↓
Phase 3: 수익 모델 + 유닛 이코노믹스 + BM Score (bm-designer helper 호출, skill-local)
    ↓
Phase 4: 전략 검증 (CSO 에이전트 호출)
    ↓
Phase 5: BM 문서 생성 (doc-loop 호출)
```

### Phase 1: 컨텍스트 수집 (이 스킬이 직접 수행)

> 파이프라인 모드: 외부 컨텍스트에 제품 설명 + 타겟 고객이 있으면 이 Phase를 건너뛴다. 필수 항목 중 빠진 것만 한 번의 질문으로 수집.

사용자에게 아래 필수 항목을 인터뷰한다:

| 항목 | 질문 예시 |
|------|----------|
| 제품/서비스 설명 | "어떤 제품인가요? 핵심 가치는?" |
| 타겟 고객 | "누가 쓰나요? B2B/B2C?" |
| 현재 수익 상태 | "지금 매출이 있나요?" |
| 경쟁 환경 | "주요 경쟁사는?" |
| 비용 구조 | "주요 비용은? (서버, 인건비, API)" |
| 제약 조건 | "예산, 일정, 규제 제약이 있나요?" |

수집 후 요약하여 사용자 확인을 받는다. 확인 없이 Phase 2로 넘어가지 않는다.

### Phase 2: 시장 조사 (bm-researcher helper 호출)

> 파이프라인 모드: 리서치 데이터가 이미 있으면 갭 분석만 수행 — 누락 항목만 bm-researcher helper에게 보충 요청.

`agents/bm-researcher.md` 본문을 Read. `general-purpose` agent를 spawn하되 prompt 구조:

```
[bm-researcher.md 본문 그대로]

---

## This invocation

### product_summary
<Phase 1의 제품/서비스 설명>

### target_segment
<Phase 1의 타겟 고객 + 지역>

### existing_research        # 파이프라인 모드만
<상위 워크플로우가 이미 가진 리서치 데이터>

### gap_list                  # 파이프라인 모드 갭 분석만
<누락 항목 목록 — 4 카테고리 중 어느 것이 비어있는지>
```

응답 YAML(`bm_research:`)을 `phase2_research`로 보관.

수집 카테고리(요약):
1. 경쟁사 3~5개의 가격/과금 모델
2. 시장 규모 (TAM/SAM/SOM)
3. 업종별 벤치마크 (CAC, LTV, Churn, ARPU)
4. 가격 민감도 신호

### Phase 3: BM 설계 (bm-designer helper 호출)

`agents/bm-designer.md` 본문을 Read. `general-purpose` agent를 spawn하되 prompt 구조:

```
[bm-designer.md 본문 그대로]

---

## This invocation

### 제품 정보
<Phase 1 수집 내용>

### 시장 데이터
<phase2_research YAML 그대로>

### 작업
수익 모델 선택, 가격 티어 설계, 유닛 이코노믹스(3시나리오), BM Score를 산출하라.
```

응답으로 수익 모델, 유닛 이코노믹스, BM Score를 포함한 `bm-design` YAML을 받아 `phase3_design`에 보관한다.

### Phase 4: 전략 검증 (CSO 에이전트 호출)

**CSO 에이전트**를 호출하여 Phase 3의 BM 설계를 검증한다:

```
다음 비즈니스 모델의 전략적 타당성을 검증하라:

{Phase 3 bm-designer 출력 전체}

검증 항목:
1. 수익 모델의 지속 가능성
2. 가격 전략의 적정성
3. 유닛 이코노믹스의 현실성
4. 스케일링 시 비용 구조 변화
5. 최대 리스크 3가지와 대응 방안
```

CSO 피드백 처리:
- **치명적 리스크** → Phase 3으로 돌아가 bm-designer에게 수정 요청 (최대 10회)
- **관리 가능한 리스크** → 대응 방안을 BM 문서에 포함
- **경미한 우려** → 모니터링 항목으로 기록

### Phase 5: BM 문서 생성 (doc-loop 호출)

**doc-loop 스킬**을 자동(B) 모드 + LLM 모드로 호출한다. Phase 1~4의 모든 산출물을 컨텍스트로 전달하여 BM 문서를 생성한다.

## 외부 컨텍스트 주입 인터페이스

상위 워크플로우가 이 스킬을 호출할 때 아래 구조를 전달한다:

```
## BM Designer 외부 컨텍스트

### 제품 정보
- 제품/서비스 설명: {설명}
- 핵심 가치 제안: {가치}
- 타겟 고객: {고객 세그먼트}
- 차별화 포인트: {경쟁 우위}

### 검증 이력 (있으면)
- CEO 제안 요약: {제안 내용}
- CSO 검증 결과: {Accept/Rebuttal + 사유}

### 리서치 데이터 (있으면)
- 시장 규모: {TAM/SAM/SOM}
- 경쟁사 분석: {경쟁사별 가격/모델}
- 업종 벤치마크: {CAC, LTV, Churn, ARPU}
```

## 경계

- 이 스킬은 **오케스트레이션만** 수행한다. 수익 모델 설계, 유닛 이코노믹스 계산, BM Score 산출은 bm-designer helper(skill-local)가 담당한다.
- 시장 조사는 bm-researcher helper(skill-local), 전략 검증은 CSO 에이전트, 문서 생성은 doc-loop 스킬이 각각 담당한다.
- bm-researcher와 bm-designer는 정식 글로벌 subagent가 아니라 _스킬 내부 instruction 파일_(`agents/bm-researcher.md`, `agents/bm-designer.md`). 메인 모델이 본문을 Read한 뒤 `general-purpose` agent의 prompt로 전달한다. 글로벌 agent namespace를 오염시키지 않으면서 NEVER #8(subagent leaf-only) 자연 충족.
- 이 스킬이 에이전트를 직접 호출하지 않는다. 메인 모델에게 에이전트 호출을 요청하고 결과를 받아 다음 Phase로 전달한다.
