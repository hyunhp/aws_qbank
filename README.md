# AWS Question Bank — GitHub Pages 배포용 정적 버전

이 폴더는 `hyunhp.github.io`(또는 다른 GitHub Pages 저장소)에 그대로 올리면 동작하는 완전한 정적 사이트입니다.
Claude Code(claude.ai)는 사용자 GitHub 계정에 쓰기 권한이 없어서 직접 push할 수 없기 때문에, 파일로 전달합니다.

## 왜 필요한가
claude.ai Artifact로 만든 원본 페이지(마스터 문제은행)는 실시간 DB를 쓰기 때문에 계속 늘어나는 문항을 자동으로 보여주지만, 로그인/조직 내부용이라 완전히 공개된 개인 사이트로 두기는 어렵습니다.
이 폴더는 그 DB의 **특정 시점 스냅샷**을 완전한 정적 파일(`data/*.json`)로 내보낸 버전이라, GitHub Pages 같은 순수 정적 호스팅에서도 그대로 작동합니다.

## 배포 방법 (택 1)

**A. 기존 hyunhp.github.io 저장소의 하위 폴더로 추가**
1. `hyunhp.github.io` 저장소를 로컬에 clone
2. 이 폴더 전체를 저장소 안에 `aws-qbank/`라는 이름으로 복사 (index.html, README.md, data/ 폴더 전부 포함)
3. `git add aws-qbank && git commit -m "Add AWS question bank" && git push`
4. 몇 분 뒤 `https://hyunhp.github.io/aws-qbank/`에서 바로 열립니다.

**B. 별도 저장소로 배포**
1. 새 저장소 생성 (예: `aws-qbank`)
2. 이 폴더 내용을 저장소 루트에 그대로 push
3. 저장소 Settings → Pages에서 GitHub Pages 활성화 (main 브랜치, `/`)
4. `https://hyunhp.github.io/aws-qbank/` 형태로 배포됨 (저장소 이름에 따라 경로 달라짐)

## 현재 포함된 데이터 (2026-09-15 최종 완료 시점 스냅샷 — 12개 자격증 전부)
- AIF-C01 (AI Practitioner): 142문항
- AIB-C01 (AI Business Strategist): 129문항
- DEA-C01 (Data Engineer – Associate): 180문항
- SAA-C03 (Solutions Architect – Associate): 162문항
- DVA-C02 (Developer – Associate): 165문항
- SOA-C03 (CloudOps Engineer – Associate): 137문항
- MLA-C01 (ML Engineer – Associate): 178문항
- SAP-C02 (Solutions Architect – Professional): 196문항
- DOP-C02 (DevOps Engineer – Professional): 225문항
- AIP-C01 (GenAI Developer – Professional): 168문항
- ANS-C01 (Advanced Networking – Specialty): 188문항
- SCS-C03 (Security – Specialty): 191문항
- **합계: 1,952문항, 12개 자격증 전체 커버** (자격증 간 공유 태깅된 문항은 두 개 이상의 카운트에 중복 포함됨)

## 갱신 방법
`data/<자격증코드>.json` 파일을 교체하기만 하면 됩니다. 마스터 문제은행(claude.ai Artifact)에 문항이 추가되면 다시 내보내 전달해드릴 수 있습니다 — 요청해주세요.
각 JSON 파일은 문항 객체 배열이며, 필드는 `id, stem, choices, correctKeys, explanation, difficulty, scenarioType, services, taskId, domainCode, examCodes`입니다.

## 딥링크
`index.html#exam=AIF-C01` 형태로 특정 자격증만 필터링된 화면으로 바로 열 수 있습니다 (뉴스레터 링크에 활용 가능).

## 인터랙티브 테스트 모드 (2026-09-16 추가)
정답이 처음부터 노출되지 않고, 실제 시험처럼 풀어볼 수 있도록 바뀌었습니다:
- 단일 정답 문항: 선택지를 클릭하면 즉시 정답/오답이 표시되고, 정답 박스가 펼쳐지며(해설 포함) 채점됩니다.
- 복수 정답 문항("복수 정답" 배지 표시): 선택지를 여러 개 클릭해 고른 뒤 "정답 확인" 버튼을 눌러야 채점됩니다.
- "정답만 보기" 링크: 풀지 않고 바로 정답만 확인하고 싶을 때 사용 — 이 경우 채점에는 반영되지 않습니다.
- "다시 풀기" 버튼: 채점 후 같은 문항을 다시 풀어볼 수 있습니다(최초 채점 결과만 점수에 반영, 재시도는 연습용).
- 상단 칩 아래에 현재 자격증의 누적 점수(정답 수 / 시도 수, %)가 표시되고, "초기화" 링크로 리셋할 수 있습니다.
- 참고: 이 인터랙티브 기능은 순수 브라우저 클릭 이벤트 기반이라 GitHub Pages 같은 일반 정적 호스팅에서는 정상 동작합니다 (claude.ai Artifact 뷰어에서 과거 겪었던 클릭 미작동 문제와는 무관한 별개의 실행 환경입니다).

## 참고
- 순수 정적 파일이라 별도 서버나 빌드 과정이 필요 없습니다 (HTML/CSS/JS + JSON뿐).
- 조직 외부에도 공개되는 완전한 퍼블릭 페이지이니, 문항 내용에 민감한 정보가 없는지 한 번 확인해 주세요 (현재는 AWS 공식 시험 가이드 기반의 오리지널 연습문제만 들어있어 문제 없을 것으로 보입니다).
