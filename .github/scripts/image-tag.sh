#!/usr/bin/env bash
# Вычисляет имя образа и тег вида <ветка>-<версия> по данным события релиза.
#
# Вход (переменные окружения):
#   GITHUB_REPOSITORY  владелец/репозиторий
#   RELEASE_TAG        github.event.release.tag_name
#   RELEASE_TARGET     github.event.release.target_commitish
#   DEFAULT_BRANCH     github.event.repository.default_branch
#
# Выход: строки image=..., tag=... и version=... в stdout (формат $GITHUB_OUTPUT).
# Все значения проходят санитизацию, поэтому их безопасно подставлять дальше.
set -euo pipefail

: "${GITHUB_REPOSITORY:?не задан GITHUB_REPOSITORY}"
: "${RELEASE_TAG:?не задан RELEASE_TAG}"
: "${RELEASE_TARGET:?не задан RELEASE_TARGET}"
: "${DEFAULT_BRANCH:?не задан DEFAULT_BRANCH}"

# GHCR не принимает заглавные буквы в имени образа.
image="ghcr.io/${GITHUB_REPOSITORY,,}"

# target_commitish не гарантирует имя ветки: при создании релиза через API туда
# можно положить SHA коммита. В этом случае берём ветку по умолчанию.
branch="$RELEASE_TARGET"
if [[ "$branch" =~ ^[0-9a-f]{40}$ ]]; then
    echo "target_commitish похож на SHA, подставляю ветку по умолчанию: $DEFAULT_BRANCH" >&2
    branch="$DEFAULT_BRANCH"
fi

# Слеши в именах веток (feature/x) и прочие недопустимые символы заменяются на
# дефис: тег Docker их не принимает.
sanitize() {
    printf '%s' "$1" | tr '/' '-' | tr -c 'a-zA-Z0-9._-' '-'
}

version="$(sanitize "$RELEASE_TAG")"
tag="$(sanitize "$branch")-${version}"

# Маска тега Docker. Если результат ей не соответствует — падаем, а не пушим мусор.
if [[ ! "$tag" =~ ^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$ ]]; then
    echo "::error::Вычисленный тег недопустим для Docker: '${tag}'" >&2
    exit 1
fi

echo "image=${image}"
echo "tag=${tag}"
echo "version=${version}"
