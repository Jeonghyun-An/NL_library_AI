#!/usr/bin/env bash
# build_dev_images.sh — dev 태그 이미지 build + push 한 방에
#
# docker-compose.dev.yml이 참조하는 landsoftdocker/nl-lib-fastapi:dev,
# landsoftdocker/nl-lib-nuxt:dev 이미지를 저장소 루트 기준으로 빌드하고
# 레지스트리에 push한다. 로컬(git-bash/WSL)에서도, 서버에서도 그대로 동작.
#
# 사용법:
#   bash scripts/build_dev_images.sh            # fastapi + nuxt 둘 다
#   bash scripts/build_dev_images.sh fastapi     # fastapi만
#   bash scripts/build_dev_images.sh nuxt        # nuxt만
#
# 이미지 이름/태그를 바꾸고 싶으면 환경변수로 override:
#   NL_LIB_FASTAPI_IMAGE=myrepo/fastapi:dev NL_LIB_NUXT_IMAGE=myrepo/nuxt:dev \
#     bash scripts/build_dev_images.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FASTAPI_IMAGE="${NL_LIB_FASTAPI_IMAGE:-landsoftdocker/nl-lib-fastapi:dev}"
NUXT_IMAGE="${NL_LIB_NUXT_IMAGE:-landsoftdocker/nl-lib-nuxt:dev}"

TARGET="${1:-all}"

build_push_fastapi() {
  echo "── FastAPI: ${FASTAPI_IMAGE} ─────────────────────"
  docker build -t "${FASTAPI_IMAGE}" "${REPO_ROOT}/app"
  docker push "${FASTAPI_IMAGE}"
}

build_push_nuxt() {
  echo "── Nuxt: ${NUXT_IMAGE} ───────────────────────────"
  docker build -t "${NUXT_IMAGE}" "${REPO_ROOT}/frontend"
  docker push "${NUXT_IMAGE}"
}

case "${TARGET}" in
  fastapi) build_push_fastapi ;;
  nuxt)    build_push_nuxt ;;
  all)     build_push_fastapi; build_push_nuxt ;;
  *)
    echo "알 수 없는 타겟: ${TARGET} (fastapi|nuxt|all 중 하나)" >&2
    exit 1
    ;;
esac

echo ""
echo "완료. Portainer에서 nl-lib-dev 스택 Pull & Redeploy 하면 반영됩니다."
