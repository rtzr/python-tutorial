# RTZR 한국어 음성 전사 파이프라인

로컬 음성 파일 한 건을 RTZR Batch STT API에 보내고, 기본 전사와 선택적으로 요청한
보정 전사 및 인사이트를 사용자가 바로 읽을 수 있는 TXT로 저장하는 작은 Python
CLI입니다. 원본 API 응답도 함께 저장합니다.

> 이 튜토리얼을 진행하려면 사전 문의가 필수입니다. 전사 결과 보정과 인사이트는
> Enterprise 기능이며, 권한이 있는 계정에서만 사용할 수 있습니다. 자세한 내용은
> [요금제 안내](https://developers.rtzr.ai/docs/pricing/#plans)를 확인하세요.

## 준비

Python 3.10 이상이 필요하며, 의존성 설치와 실행에는 [uv](https://docs.astral.sh/uv/)를 사용합니다.

프로젝트 디렉터리에서 다음 명령을 실행합니다.

```bash
uv sync --locked
cp -n .env.example .env
```

`.env`에는 발급받은 credential과 사용할 API 호스트를 입력합니다. 같은 이름의 환경
변수에 비어 있지 않은 값이 있으면 환경 변수 값이 우선합니다. `.env`는 명령을 실행하는
현재 디렉터리에서 읽습니다.

```dotenv
RTZR_CLIENT_ID=...
RTZR_CLIENT_SECRET=...
RTZR_BASE_URL=https://openapi.vito.ai
```

credential과 access token은 터미널이나 결과 파일에 기록하지 않습니다.

## 실행

아래 예시의 `sample.wav`는 사용할 로컬 음성 파일의 경로로 바꿔주세요.

음성 파일만 전달하면 기본 STT를 수행하고 UTC 시각을 포함한 결과 디렉터리를 자동으로
만듭니다.

```bash
uv run --locked rtzr-transcribe sample.wav
```

보정과 인사이트가 모두 필요하다면 각 옵션을 함께 지정합니다. 결과 위치나 인사이트
관점도 직접 정할 수 있습니다. 지정한 결과 디렉터리는 존재하지 않거나 비어 있어야
합니다.

```bash
uv run --locked rtzr-transcribe sample.wav \
  --output-dir outputs/meeting \
  --refinement \
  --insight \
  --insight-prompt "회의의 결정 사항과 후속 작업을 정리해 주세요."
```

기본 인사이트 지시문은 음성의 핵심 내용과 중요한 요청·결정·후속 조치를 한국어로
간결하게 정리하도록 요청합니다. `--insight --insight-prompt ""`로 빈 값을 명시하면
인사이트 기능은 유지하되 지시문은 API에 전송하지 않습니다. `--insight-prompt`는
반드시 `--insight`와 함께 사용해야 합니다. `--timeout <초>`는 음성 업로드와 작업 생성이 끝난 뒤 전사 결과를 기다릴 시간을 설정합니다. 기본값은 1시간입니다. 이미 시작된 결과 조회 요청이나 자동 재시도는 바로 중단되지 않으므로 실제 실행 시간은 설정값보다 길어질 수 있습니다.

보정이나 인사이트 중 필요한 기능만 독립적으로 켤 수도 있습니다.

```bash
uv run --locked rtzr-transcribe sample.wav --refinement
uv run --locked rtzr-transcribe sample.wav --insight
```

Enterprise 권한이 없는 계정에서 두 옵션을 사용하면 CLI가 요금제 안내와 함께 종료합니다.

`--refinement`와 `--insight`를 생략하면 기본 STT만 요청합니다.

모든 전사 요청에는 화자 분리가 기본으로 적용됩니다. 화자 수는 RTZR가 자동으로
예측하지만, 참여 인원을 알고 있다면 선택 옵션으로 지정할 수 있습니다.

```bash
uv run --locked rtzr-transcribe sample.wav --speaker-count 2
```

`--speaker-count`에는 1 이상의 정수를 입력하며, 생략하면 자동 예측을 사용합니다. 

### 기본 요청 설정

- 모델: `sommers`
- 언어: 한국어(`ko`)
- 도메인: `GENERAL`
- 화자 분리: 사용, 화자 수는 자동 예측
- 보정·인사이트: 기본 비활성화, 각 CLI 옵션으로 활성화

```bash
uv run --locked rtzr-transcribe --help
```

## 지원 형식과 전처리

다음 RTZR 공식 지원 형식을 대소문자 구분 없이 받습니다.

- `mp4`
- `m4a`
- `mp3`
- `amr`
- `flac`
- `wav`

## 결과

```text
outputs/<음원명>-<UTC 실행시각>/
├── transcript.txt  # 화자별 최종 전사(--refinement 사용 시 보정 전사)
├── insight.txt     # 제목, 분류, 내용(--insight 사용 시 생성)
├── response.json   # 기본 전사 원본 응답
└── refined.json    # 보정 결과 원본 응답(--refinement 사용 시 생성)
```

전사와 파일 저장이 정상적으로 완료되면 `response.json`과 `transcript.txt`가 생성됩니다.
`--insight`를 사용하면 `response.json`의 `results.insight`와 별개로 읽기 쉬운
`insight.txt`가 생성됩니다.
`--refinement`를 사용하면 `refined.json`이 생성되고 `transcript.txt`에는 보정 전사가
저장됩니다. 옵션을 생략하면 해당 추가 파일은 생성되지 않습니다.

전사 생성 POST는 서버가 작업을 받았는지 모호할 때 중복 작업을 만들지 않도록 자동
재시도하지 않습니다. 결과 조회는 공식 권장 주기인 5초마다 수행하며 일시적인 네트워크
오류, 429와 일부 5xx만 제한적으로 재시도합니다.

## 테스트

```bash
make check
```

자동 테스트는 mock 응답만 사용하고 실제 API를 호출하지 않습니다.

실제 API로 보정 기능을 확인하려면 준비한 로컬 음원으로 CLI를 실행합니다.
이 명령은 실제 전사 요청을 생성하므로 계정의 사용량과 요금에 유의하세요.

```bash
uv run --locked rtzr-transcribe sample.wav --refinement
```

결과는 일반 실행과 동일하게 `outputs/<음원명>-<UTC 실행시각>/`에 저장됩니다.

## 공식 문서

- [인증 가이드](https://developers.rtzr.ai/docs/authentications/)
- [일반 STT](https://developers.rtzr.ai/docs/stt-file/)
- [화자 분리](https://developers.rtzr.ai/docs/stt-file/diarization/)
- [전사 결과 보정](https://developers.rtzr.ai/docs/stt-file/refinement/)
- [인사이트](https://developers.rtzr.ai/docs/stt-file/insight/)
