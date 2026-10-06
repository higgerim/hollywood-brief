#!/bin/bash
# 더블클릭하면 GitHub에서 검토 중인 초안을 받아 '검토용' 폴더에 날짜별로 풀어요.
# 이미 받은 날짜도 GitHub에서 고친 내용이 있으면 새로 덮어써요. 승인·종료된 초안은 지워요.
cd "$(dirname "$0")" || exit 1
OUT="검토용"
mkdir -p "$OUT"

echo "GitHub에서 최신 초안을 확인하는 중..."
git fetch -q --prune origin || { echo "GitHub 연결에 실패했어요. 인터넷 연결을 확인해 주세요."; read -r -p "Enter를 누르면 닫혀요"; exit 1; }

dates=$(git for-each-ref --format='%(refname:lstrip=4)' 'refs/remotes/origin/draft/*' | sort)
for d in $dates; do
  rm -rf "${OUT:?}/$d"
  git archive "origin/draft/$d" "drafts/$d" | tar -x -C "$OUT" --strip-components=1
  echo "  $d: 카드 $(ls "$OUT/$d/cards" 2>/dev/null | wc -l | tr -d ' ')장"
done

# GitHub에서 승인·종료돼 브랜치가 사라진 초안은 정리해요
for dir in "$OUT"/*/; do
  [ -d "$dir" ] || continue
  d=$(basename "$dir")
  echo "$dates" | grep -qx "$d" || { rm -rf "$dir"; echo "  $d: 검토가 끝나서 지웠어요"; }
done

[ -z "$dates" ] && echo "검토 중인 초안이 없어요."
latest=$(echo "$dates" | tail -1)
open "$OUT/${latest:+$latest/cards}"
