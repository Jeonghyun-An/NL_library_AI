// frontend/utils/brand.ts
// 화면에 보이는 제품 기능 이름. 사용자 결정(2026-10-12): 딥리서치는 영문 DeepResearch 로, 붙여 쓴다(DeepRead 와 짝).
// 화면 문구·파일 이름·문서 속성은 이 상수를 쓴다 — 표기를 바꿀 때 여기 한 곳만 고친다. 슬래시 명령(/deep-research)·내부 id 는 그대로다.
export const DEEP_RESEARCH = "DeepResearch";
// 짝인 논문·책 1편과의 대화 — round08 화면이 쓰는 표기(DeepRead) 그대로. 06e 화면 글(단계 화면 오른쪽 패널 탭·온보딩)이 이 상수를 쓴다
export const DEEP_READ = "DeepRead";

// 로딩 스피너 — 스스로 도는 160×160 GIF(투명 배경, CSS 회전 없음). 사용자가 '뚱뚱 입체'로 바꾸려면 SPINNER_SRC 한 줄만 SPINNER_VARIANTS.bold 로 고친다.
// 원본(800·512px, 약 2MB)을 줄인 파일이다(만든 방법: research/spinner-160/make_160.py).
export const SPINNER_VARIANTS = {
  /** 깔끔 — 가는 선(기본) */
  clean: "/skovix-spinner-clean-160.gif",
  /** 뚱뚱 입체 — 두꺼운 음영 */
  bold: "/skovix-spinner-bold-160.gif",
} as const;
export const SPINNER_SRC: string = SPINNER_VARIANTS.clean;
// SKOVIX 심볼(깔끔 스피너의 정면 프레임 — S 고리와 별, 160px). 결과 AI 패널 로고가 끝났을 때의 정지 그림과 슬래시 명령 목록의
// 아이콘(사용자 결정 2026-10-14)이 같은 그림을 쓴다
export const SYMBOL_SRC = "/skovix-spinner-front-160.png";
export const SPINNER_DONE_SRC = SYMBOL_SRC;
