# 할리우드 브리핑 자동화

해외 할리우드 이슈를 모아 한국어 카드뉴스(인스타그램)와 뉴스레터(메일리) 초안을 자동으로 만들어요.

## 이렇게 돌아가요

```
월·수·금 오전 6시  ─ GitHub Actions가 자동 실행
                    기사 수집(RSS 7곳 + 레딧) → 화제성 순 정렬 → Claude가 6개 선별·원고 작성
                    → 카드뉴스 8장 + 뉴스레터 본문 + 캡션 생성 → 검토용 PR 생성
나 (10~15분)       ─ PR에서 검토 → 필요하면 content.json 수정 (카드 자동 재생성) → Merge
Merge 직후         ─ 인스타그램 캐러셀 자동 게시
나 (5분)           ─ 뉴스레터 페이지를 열어 복사 → 메일리에 붙여넣고 발행
```

## 처음 한 번만 하는 설정

### 1. GitHub 저장소 만들기
1. [github.com](https://github.com)에 가입하고 **New repository**를 누르세요. 이름은 `hollywood-brief`, 공개 범위는 **Public**으로 하세요.
   > 인스타그램이 카드 이미지를 공개 주소로 가져가기 때문에 **Public**이어야 해요. API 키 같은 비밀번호는 Secrets에 따로 저장되니 공개되지 않아요.
2. 이 폴더를 올리세요.
   ```bash
   cd ~/hollywood-brief
   git init && git add . && git commit -m "첫 커밋"
   git branch -M main
   git remote add origin https://github.com/higgerim/hollywood-brief.git
   git push -u origin main
   ```
3. 저장소 **Settings → Actions → General**에서 아래 두 가지를 설정하세요.
   - Workflow permissions: **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**

### 2. Claude 구독 토큰 (추가 비용 없음)
원고 작성은 Claude 구독 계정으로 실행돼요. 구독 사용 한도를 같이 써요.
1. 터미널에서 아래 명령을 실행하세요. 브라우저가 열리면 로그인하고 승인하세요.
   ```bash
   ~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64/resources/native-binary/claude setup-token
   ```
   > 확장 프로그램 버전이 여러 개 설치되어 있으면 가장 높은 버전의 경로를 쓰세요.
2. 터미널에 출력된 토큰(`sk-ant-oat...`)을 복사하세요.
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 등록하세요.
   - `CLAUDE_CODE_OAUTH_TOKEN` = 복사한 토큰
4. 토큰은 **1년 동안 유효해요.** 만료되면 같은 방법으로 다시 발급받아 등록하세요.

> 구독 한도가 부족해지면 [config.yaml](config.yaml)의 `engine`을 `"api"`로 바꾸세요. 그다음 [console.anthropic.com](https://console.anthropic.com)에서 API 키를 발급받아 `ANTHROPIC_API_KEY` Secret으로 등록하면 돼요. 이 방식은 쓴 만큼 별도로 결제돼요.

### 3. 인스타그램 연결
1. 인스타그램 앱에서 새 계정을 만드세요. 그다음 **설정 → 계정 유형 및 도구 → 프로페셔널 계정으로 전환 → 비즈니스**를 선택하세요.
2. [developers.facebook.com](https://developers.facebook.com)에서 **앱 만들기**를 누르고, 사용 사례로 **Instagram API**를 고르세요.
3. 앱 대시보드의 **Instagram → Instagram 로그인을 통한 API 설정**에서 아래 순서로 진행하세요.
   - **계정 추가**로 만든 인스타그램 계정을 연결하세요.
   - **토큰 생성**을 눌러 액세스 토큰을 복사하세요. 계정 ID도 같은 화면에 나와요.
4. Secrets에 등록하세요.
   - `IG_USER_ID` = 인스타그램 계정 ID(숫자)
   - `IG_ACCESS_TOKEN` = 액세스 토큰

### 4. 토큰 자동 연장용 GitHub 토큰
인스타그램 토큰은 60일이 지나면 만료돼요. 매달 자동으로 연장하려면 Secrets를 수정할 수 있는 GitHub 토큰이 필요해요.
1. GitHub **Settings → Developer settings → Fine-grained tokens → Generate new token**으로 가세요.
2. Repository access에서 `hollywood-brief`를 고르고, Permissions에서 **Secrets: Read and write**를 주세요.
3. Secrets에 `GH_SECRETS_TOKEN`으로 등록하세요.

### 5. 뉴스레터 페이지 켜기 (GitHub Pages)
메일리에 사진째로 복사해 붙일 수 있는 뉴스레터 페이지를 만들어요.
1. 저장소 **Settings → Pages**로 가세요.
2. Source는 **Deploy from a branch**, Branch는 **main** / **(root)**로 고르고 **Save**를 누르세요.
3. 이후 Merge할 때마다 `https://higgerim.github.io/hollywood-brief/drafts/날짜/newsletter.html` 주소로 페이지가 열려요. PR 본문에 링크가 있어요.

### 6. 브랜드 설정
[config.yaml](config.yaml)에서 소식지 이름, 인스타 핸들, 메일리 주소를 바꾸세요.

### 7. 첫 실행
저장소의 **Actions → 1. 초안 만들기 → Run workflow**를 누르면 몇 분 뒤 PR이 올라와요.

## 평소 운영

| 할 일 | 방법 |
|---|---|
| 초안 검토 | PR의 **Files changed** 탭에서 카드 이미지와 `newsletter.md`를 확인해요 |
| 문구 수정 | `content.json`의 연필 아이콘으로 수정하고 커밋해요 → 1~2분 뒤 카드가 자동으로 다시 만들어져요 |
| 승인·게시 | **Merge pull request**를 누르면 인스타그램에 자동 게시돼요 |
| 뉴스레터 | Merge 1~2분 뒤 PR 본문의 **뉴스레터 페이지** 링크를 열어요 → 안내 상자 아래부터 끝까지 드래그해 복사 → 메일리 에디터에 붙여넣고 발행해요. 사진과 링크가 함께 옮겨져요 |
| 이번 호 건너뛰기 | PR을 **Close**해요 |
| 수집 매체 추가 | `config.yaml`의 `feeds`에 RSS 주소를 추가해요 |
| 사진 바꾸기 | `content.json`에서 해당 이슈의 `image_people`(인물 영어 위키백과 문서 제목, 예: `["Taylor Swift", "Travis Kelce"]`)나 `image_focus`(`people`/`work`), `image_work`(앨범·영화·드라마)를 고쳐요. 특정 사진을 쓰려면 공용 파일 이름(예: `"File:xxx.jpg"`)을 넣어요. 사진을 빼려면 `image_people`를 `[]`, `image_work`의 `kind`를 `"none"`으로 둬요 |
| 카드 디자인 변경 | [hbrief/templates/card.html](hbrief/templates/card.html)의 색상과 글꼴을 수정해요 |

## 콘텐츠 원칙 (코드에 반영되어 있어요)
- 원문을 번역하지 않고 요약과 해설만 써요. 출처 링크는 AI가 아니라 실제 수집한 기사에서 붙여요.
- 이미지는 **소식의 장면에 가까운 순서**로 골라요. 카드·캡션·뉴스레터에 출처를 자동으로 표기해요.
  - 인물 중심 소식: 등장인물이 함께 찍힌 사진 → 두 사람 사진 나란히(예: 테일러 스위프트 | 트래비스 켈시) → 관련 작품 → 한 사람 사진
  - 작품 중심 소식(신작·리뷰 등): 앨범 커버(Apple Music)나 공식 포스터(위키백과) → 인물 사진
  - 인물 사진은 위키미디어 공용의 **자유 라이선스(CC BY, CC BY-SA, CC0, 퍼블릭 도메인)** 사진만 써요. 앨범 커버·포스터는 공식 홍보 이미지를 보도·비평 목적으로 인용해요.
  - 기사에 실린 사진(Getty, AP 등 통신사 사진)이나 AI로 만든 인물 이미지는 쓰지 않아요. 저작권과 초상권 문제 때문이에요. 쓸 이미지가 없으면 텍스트 카드로 만들어요.
- 확인 수준을 `확인됨 / 보도 / 루머`로 나눠 표시해요. 루머는 카드에 "미확인 보도" 배지가 붙어요.
- AI 초안에는 사실 오류가 섞일 수 있어요. **Merge 전 사람 검토는 꼭 해 주세요.**

## 예상 비용
- Claude: 구독 계정을 쓰면 추가 비용이 없어요. `engine: api`로 바꾸면 1회에 약 $0.3~0.5가 들어요.
- GitHub Actions: Public 저장소는 무료예요.
- 메일리: 브랜딩 플랜이 필요해요. 무료 플랜은 월 4회까지만 발행할 수 있어요.

## 로컬에서 테스트하기
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
# 예시 원고로 카드 만들어 보기 (API 키 불필요)
mkdir -p /tmp/sample && cp examples/sample-content.json /tmp/sample/content.json
.venv/bin/python -m hbrief render /tmp/sample && open /tmp/sample/cards
```
