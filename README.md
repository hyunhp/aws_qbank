# AWS Question Bank 
- LINK: `https://hyunhp.github.io/aws_qbank/`
  
## 현재 포함된 데이터 (2026-09-24 스냅샷)
- AIF-C01 (AI Practitioner): 142문항
- AIB-C01 (AI Business Strategist): 148문항 (고난도 19문항 추가)
- DEA-C01 (Data Engineer – Associate): 199문항 (고난도 19문항 추가)
- SAA-C03 (Solutions Architect – Associate): 182문항 (고난도 20문항 추가)
- DVA-C02 (Developer – Associate): 184문항 (고난도 19문항 추가)
- SOA-C03 (CloudOps Engineer – Associate): 157문항 (고난도 20문항 추가)
- MLA-C01 (ML Engineer – Associate): 197문항 (고난도 19문항 추가)
- SAP-C02 (Solutions Architect – Professional): 216문항 (고난도 20문항 추가)
- DOP-C02 (DevOps Engineer – Professional): 244문항 (고난도 19문항 추가)
- AIP-C01 (GenAI Developer – Professional): 208문항 (고난도 41문항 추가, 테스트용 더미 1문항 제거)
- ANS-C01 (Advanced Networking – Specialty): 208문항 (고난도 20문항 추가)
- SCS-C03 (Security – Specialty): 211문항 (고난도 20문항 추가)
- **12개 자격증 노출** (자격증 간 공유 태깅된 문항은 두 개 이상의 카운트에 중복 포함됨)


## 해설 아키텍처 다이어그램 (2026-09 진행 중)

- SAA-C03 / SAP-C02 문항 중 구조가 핵심인 문항의 해설에 정답 아키텍처 다이어그램을 표시 (정답 확인 후에만 보임).
- 브라우저에서 `js/diagram.js`가 `diagrams/<문항ID>.json` 설계도를 그려서 표시하고, 해설을 처음 열 때만 불러옴. 실패해도 해설 텍스트와 퀴즈 기능에는 영향 없음.
- 도구·형식 설명: `tools/diagrams/README.md`
- 아이콘: [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) (AWS 제공, 아키텍처 다이어그램 용도)

## 정답 위치 재배치 (2026-09-24)
- 기존 문항은 정답이 A/B에 몰려 있어(A 61%, B 35%) 문항 ID 기반 시드로 보기 순서를 섞음. 해설 속 보기 문자 참조("Option B", "(A, D)" 등)도 새 위치로 함께 변환.
- 스크립트: `tools/rebalance_answers.py` (결정적이라 다시 실행해도 같은 결과; 마스터 DB에서 재추출한 경우 export 후 한 번 실행)

## 오답 보기 보강 ("가장 긴 보기 = 정답" 단서 제거)
- 오답 보기에 그럴듯한 근거를 붙이거나 정답의 불필요한 부연을 줄여, 보기 길이만으로 정답을 고를 수 없게 조정. 오답의 핵심 오류는 유지해 해설과 일치.
- 변경 내역: `tools/distractor_rewrites/<자격증>.json` ({문항ID: {보기키: 새 텍스트}}) — 사이트 데이터 기준 보기 키.
- 최종 분포 (단일 정답 문항 중 정답이 가장 긴 비율 / 가장 짧은 비율):

| 자격증 | 가장 김 | 가장 짧음 |
|---|---|---|
| AIF-C01 | 21% | 24% |
| AIB-C01 | 22% | 27% |
| DEA-C01 | 19% | 32% |
| SAA-C03 | 12% | 32% |
| DVA-C02 | 16% | 25% |
| SOA-C03 | 16% | 29% |
| MLA-C01 | 18% | 24% |
| SAP-C02 | 12% | 26% |
| DOP-C02 | 10% | 28% |
| AIP-C01 | 19% | 29% |
| ANS-C01 | 16% | 14% |
| SCS-C03 | 18% | 20% |

- 4지선다에서 무작위 기준값은 각 25%. 어느 쪽으로도 단서가 되지 않도록 맞춤.

## 기존 문항 고난도화 (difficulty=basic → 시나리오형)
- basic 문항 492개 전부를 제약 조건이 여러 개인 시나리오형 문항으로 재작성. 현재 난이도 분포: advanced 1,361 / applied 826 / basic 0.
- 변경 내역(문항 전체): `tools/hardened/<자격증>.json`

## 전 문항 상세 해설 (2026-09-24 완료)
- 전체 2,187개 고유 문항의 해설을 **정답 근거 → 오답별 이유(보기마다 한 줄) → 핵심 포인트** 구조로 통일.
- 재작성 문항은 `tools/hardened/`, 나머지 문항의 해설은 `tools/explanations/<자격증>.json`에 기록.
- 사이트: 긴 해설이 잘리지 않도록 표시 높이를 늘리고 줄바꿈을 유지.

## 사실·정답 위치 수정
- `tools/factual_fixes.json`: Q001485(Guardrails 프롬프트 공격 필터 적용 대상), Q001510(데이터 이벤트 예시를 InvokeAgent로 수정), Q001998(오답 보강 중 C/D 텍스트가 뒤바뀐 것을 복원).
- 전 문항 정답 위치 감사: 보강 전 원본과 보강 후 보기를 대조해 정답 내용이 다른 키로 옮겨간 문항이 없는지 확인(Q001998 외 이상 없음).
