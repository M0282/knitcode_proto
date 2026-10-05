# v0.6 분석 및 HTML 생성 알고리즘

## 전체 처리 흐름

```text
로컬 폴더 또는 GitHub 저장소·Issues·PR URL
  → 입력 정규화와 임시 clone
  → Python 파일 탐색·제외 규칙 적용
  → 인코딩 감지·파일 읽기·AST 파싱
  → 정의·소속·시그니처·docstring·import·호출 위치 수집
  → 내부 import graph와 함수 call graph 구성
  → Git 동시 수정 이력과 Jaccard 계산
  → 변경 파일·심볼에서 역방향 영향 전파
  → 테스트 후보·공개 API·호환성 변화 계산
  → 진입점·파일 트리·권장 읽기 순서 생성
  → 하나의 result 객체 확정
  → JSON / Markdown / self-contained HTML 렌더링
  → 산출물 크기·SHA-256 manifest 기록
```

## 1. 입력과 소스 준비

`repository_source.py`는 로컬 경로와 GitHub URL을 구분한다. GitHub의 `/issues`, `/pull/...` 같은 하위 URL은 `https://github.com/{owner}/{repository}.git` 형태로 정규화한다. 원격 입력은 임시 폴더에 clone하며 보고서에는 임시 폴더명 대신 owner와 실제 저장소명을 기록한다.

## 2. AST 구조 수집

`python_analyzer.py`는 제외 디렉터리를 건너뛰고 `.py` 파일을 수집한다. PEP 263 인코딩 선언을 감지해 읽고, 실패하면 UTF-8 대체 디코딩을 수행하면서 진단을 남긴다. 읽기 전후의 크기와 수정 시간을 비교해 분석 도중 변경된 파일도 기록한다.

각 파일에서 다음 정보를 수집한다.

- 모듈·클래스·함수 docstring
- 클래스, 함수, 비동기 함수, 메서드와 중첩 함수의 소속과 위치
- 매개변수 종류·기본값·타입 주석과 반환 타입
- 상속 대상과 데코레이터
- import 모듈·심볼·별칭·상대 import
- 호출 원문, 줄 번호, 호출자가 속한 함수와 클래스
- `obj = Class()` 형태의 인스턴스 생성 단서
- `if __name__ == "__main__"`와 그 안의 첫 호출
- 구문 오류, SyntaxWarning, 인코딩과 읽기 진단

## 3. 관계 해석

`impact.connections()`는 모듈 경로와 명시적인 import를 연결해 파일 간 방향 그래프를 만든다. `call_graph.build_call_graph()`는 다음 우선순위로 호출 대상을 해석한다.

1. 같은 파일의 정의와 `self.method()`
2. 명시적으로 import한 함수·클래스·모듈 별칭
3. 생성된 객체의 클래스에 있는 메서드
4. 저장소에서 이름이 유일한 정의

관계에는 `static`, `inferred_instance`, `unique_name_heuristic` 신뢰도를 붙인다. 연결되지 않은 호출은 내장 함수, 외부 import, 동적 속성 호출, 정의 미확인 이름으로 분류하며 원문과 위치를 모두 보존한다.

## 4. 변경 영향과 테스트 후보

변경 파일을 시작점으로 내부 import graph를 역방향 탐색한다. 변경 심볼이 지정되면 call graph 역시 역방향 너비 우선 탐색해 직접 호출자를 거리 1, 간접 호출자를 거리 2 이상으로 기록한다. 파일별 근거는 다음처럼 분리한다.

- `changed`: 직접 변경
- `imports_affected_file`: 변경 파일을 import
- `calls_changed_function`: 변경된 심볼의 호출자
- `historical_cochange`: Git에서 반복적으로 함께 수정

테스트 경로·파일명 규칙과 호출 전파 결과를 결합해 우선 실행할 테스트 파일과 함수 후보를 만든다. 이 결과는 실행 보장이 아닌 정적 검토 후보이다.

## 5. Git 동시 수정과 API 비교

Git 분석은 merge commit을 제외한 최근 커밋에서 함께 바뀐 Python 파일 쌍을 집계한다. 너무 많은 파일을 바꾼 커밋은 노이즈 방지를 위해 제외하고, 공동 변경 횟수와 Jaccard 값을 기록한다.

API surface는 공개·비공개·dunder 심볼, 시그니처, 상속, 데코레이터와 docstring을 저장한다. `--base`가 있으면 기준 리비전의 Python 파일을 임시로 복원해 현재 코드와 비교하고 다음 변화를 분류한다.

- 공개 심볼 삭제
- 함수·메서드의 매개변수 또는 반환 타입 변경
- 클래스 상속 변경
- 새 심볼 추가

## 6. 진입점과 읽기 안내

`project_insight.py`는 `__main__.py`와 main guard를 진입점 후보로 선택한다. 후보가 없으면 들어오는 호출이 없는 모듈 노드를 대안으로 사용한다. 이후 call graph를 너비 우선으로 탐색해 권장 읽기 순서, 깊이, 순환·재방문과 탐색 생략 여부를 기록한다.

## 7. HTML 생성

`html_report.py`는 앞 단계에서 확정된 `result`만 입력으로 받는다. 분석을 다시 수행하거나 별도 수치를 계산하지 않으므로 JSON과 HTML의 근거가 동일하다.

생성 순서는 다음과 같다.

1. 요약 지표와 저장소 메타데이터 계산
2. 진입점·파일 트리·영향·테스트·전파 표 생성
3. 전체 내부 import·호출·미해결 호출 표 생성
4. 공개 API와 API 변화 표 생성
5. 파일별 상세 카드와 Git·진단 섹션 생성
6. 모든 외부 문자열을 `html.escape(..., quote=True)`로 이스케이프
7. CSS와 검색 JavaScript를 포함한 단일 UTF-8 HTML로 저장

HTML은 외부 CDN을 사용하지 않는다. 검색 필드는 각 행의 `data-search` 값을 소문자로 비교해 일치하지 않는 행만 숨긴다. 모든 원자료는 JSON에도 남아 있어 별도 Graphviz나 웹 시각화로 확장할 수 있다.

## 8. 산출물 일관성

CLI는 하나의 `result`에서 `analysis.json`, `report.md`, `report.html`, `call_graph.json`, `api_surface.json`을 생성한다. `manifest.json`은 result snapshot의 SHA-256과 각 파일의 크기·SHA-256을 기록한다. 기존 v0.5 사용자를 위해 `impact.json`과 `impact.md`도 같은 내용의 호환 파일로 출력한다.

## 한계

- Python 정적 분석만 지원한다.
- 동적 import, fixture 주입, monkeypatch, 콜백과 런타임 디스패치는 놓칠 수 있다.
- 외부 라이브러리 내부 호출은 분석하지 않는다.
- Git 동시 수정은 코드 의존성이 아닌 경험적 상관관계다.
- 이름 유일성 기반 호출 관계는 낮은 신뢰도의 후보이다.
- 테스트 미검출은 테스트 영향이 없다는 뜻이 아니다.
