# AWS Question Bank — GitHub Pages 배포용 정적 버전

## 왜 필요한가
claude.ai Artifact로 만든 원본 페이지(마스터 문제은행)는 실시간 DB를 쓰기 때문에 계속 늘어나는 문항을 자동으로 보여주지만, 로그인/조직 내부용이라 완전히 공개된 개인 사이트로 두기는 어렵습니다.
폴더는 그 DB의 **특정 시점 스냅샷**을 완전한 정적 파일(`data/*.json`)로 내보낸 버전이라, GitHub Pages 같은 순수 정적 호스팅에서도 그대로 작동합니다.

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

## 참고
- LINK: `https://hyunhp.github.io/aws-qbank/`
