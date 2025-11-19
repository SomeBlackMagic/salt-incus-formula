#!/usr/bin/env bash
set -euo pipefail


#REPO_ROOT="${1:-$(pwd)}"
#FORMULA_DIR="${REPO_ROOT}"
#
#TMP_DIR="$(mktemp -d /tmp/salt-minion-XXXXXX)"
#CACHE_DIR="${TMP_DIR}/cache"
#
#mkdir -p "${TMP_DIR}/pki/minion"
#mkdir -p "${CACHE_DIR}"
#
#echo "test-minion" > "${TMP_DIR}/minion_id"
#touch "${TMP_DIR}/pki/minion/minion.pem"
#
#cat > "${TMP_DIR}/minion" <<EOF
#id: test-minion
#root_dir: ${TMP_DIR}
#
#file_client: local
#cachedir: ${CACHE_DIR}
#renderers: incus_jinja, jinja, yaml
#
#render_pipes: True
#
#file_roots:
#  base:
#    - ${REPO_ROOT}
#
#pillar_roots:
#  base:
#    - ${FORMULA_DIR}/tests/integration/_pillars
#
#module_dirs:
#  - ${FORMULA_DIR}/_modules
#
#states_dirs:
#  - ${FORMULA_DIR}/_states
#
#
#renderer_dirs:
#  - ${FORMULA_DIR}/tests/integration/_renderers
#
#
#log_file: ${TMP_DIR}/minion.log
#EOF
#
##salt-call --local --config-dir="${TMP_DIR}" saltutil.sync_all
##salt-call --local --config-dir="${TMP_DIR}" sys.list_functions | grep incus
##salt-call --local --config-dir="${TMP_DIR}" sys.list_modules
##salt-call --local --config-dir="${TMP_DIR}" sys.list_state_modules
##salt-call --local --config-dir="${TMP_DIR}" sys.list_state_functions
##salt-call --local --config-dir="${TMP_DIR}" config.get file_roots
##salt-call --local --config-dir="${TMP_DIR}" cp.list_states
#
#
#salt-call \
#  --local \
#  -l debug \
#  --config-dir="${TMP_DIR}" \
#  --out=json \
#  state.apply profiles \
#  pillar="{\"incus\": {\"profiles\": {\"prof_min\": {\"ensure\": \"present\", \"config\": {\"limits.cpu\": \"2\"}, \"devices\": {\"root\": {\"path\": \"/\", \"pool\": \"default\", \"type\": \"disk\"}}, \"description\": \"Minimal profile\"}}}}" \
#| jq
#
