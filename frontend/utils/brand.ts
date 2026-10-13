// frontend/utils/brand.ts
// 화면에 보이는 제품 기능 이름. 사용자 결정(2026-10-12): 딥리서치는 영문 DeepResearch 로, 붙여 쓴다(DeepRead 와 짝).
// 화면 문구·파일 이름·문서 속성은 이 상수를 쓴다 — 표기를 바꿀 때 여기 한 곳만 고친다. 슬래시 명령(/deep-research)·내부 id 는 그대로다.
export const DEEP_RESEARCH = "DeepResearch";

// 로딩 스피너 — 스스로 도는 160×160 GIF(투명 배경, CSS 회전 없음). 사용자가 '뚱뚱 입체'로 바꾸려면 SPINNER_SRC 한 줄만 SPINNER_VARIANTS.bold 로 고친다.
// 원본(800·512px, 약 2MB)을 줄인 파일이다(만든 방법: research/spinner-160/make_160.py).
export const SPINNER_VARIANTS = {
  /** 깔끔 — 가는 선(기본) */
  clean: "/skovix-spinner-clean-160.gif",
  /** 뚱뚱 입체 — 두꺼운 음영 */
  bold: "/skovix-spinner-bold-160.gif",
} as const;
export const SPINNER_SRC: string = SPINNER_VARIANTS.clean;
// 결과 AI 패널 로고가 끝났을 때 보이는 정지 그림(깔끔 스피너의 정면 프레임, 160px)
export const SPINNER_DONE_SRC = "/skovix-spinner-front-160.png";
