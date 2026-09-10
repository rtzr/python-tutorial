# 모델 추론 예제

아래 코드는 각 프로젝트가 공개한 공식 튜토리얼의 핵심 추론 흐름에 실제 실험 설정을 반영해 정리한 것이다.

- 공식 튜토리얼 확인일: 2026-09-08

<a id="whisper"></a>
## Whisper

- 공식 튜토리얼: [Whisper large-v3-turbo 모델 페이지](https://huggingface.co/openai/whisper-large-v3-turbo)

```python
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

model_id = "openai/whisper-large-v3-turbo"
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=True,
    use_safetensors=True,
)
model.to(device)
processor = AutoProcessor.from_pretrained(model_id)
pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device,
)
result = pipe(
    "audio.wav",
    return_timestamps=True,
    generate_kwargs={"task": "transcribe"},
)
```

실험 설정:

- 언어 자동 감지, `task="transcribe"`, 문장 단위 timestamp

<a id="qwen3-asr"></a>
## Qwen3-ASR

- 공식 튜토리얼: [Qwen3-ASR-1.7B 모델 페이지](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)

```python
import torch
from qwen_asr import Qwen3ASRModel

model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-1.7B",
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_new_tokens=2048,
)
results = model.transcribe(audio="audio.wav", language=None)
text = results[0].text
```

실험 설정:

- 언어 자동 감지, `max_new_tokens=2048`, timestamp·Forced Aligner 미사용

<a id="nemotron-35-asr"></a>
## Nemotron 3.5 ASR

- 공식 튜토리얼: [Nemotron 3.5 ASR 모델 페이지](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)

```python
from transformers import AutoModelForRNNT, AutoProcessor
from transformers.audio_utils import load_audio

model_id = "nvidia/nemotron-3.5-asr-streaming-0.6b"
processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForRNNT.from_pretrained(model_id, device_map="auto")

sampling_rate = processor.feature_extractor.sampling_rate
audio = load_audio("audio.wav", sampling_rate=sampling_rate)
inputs = processor(
    audio,
    sampling_rate=sampling_rate,
    language="auto",
    return_tensors="pt",
)
inputs = inputs.to(model.device, dtype=model.dtype)
output = model.generate(**inputs, return_dict_in_generate=True)
text = processor.decode(output.sequences[0], skip_special_tokens=True)
```

실험 설정:

- `language="auto"`, offline transcription, mono 16 kHz 입력

<a id="vibevoice-asr"></a>
## VibeVoice-ASR

- 공식 튜토리얼: [파일 추론 예제](https://github.com/microsoft/VibeVoice/blob/main/demo/vibevoice_asr_inference_from_file.py)

```python
import torch
from vibevoice.modular.modeling_vibevoice_asr import (
    VibeVoiceASRForConditionalGeneration,
)
from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor

model_id = "microsoft/VibeVoice-ASR"
processor = VibeVoiceASRProcessor.from_pretrained(
    model_id,
    language_model_pretrained_name="Qwen/Qwen2.5-7B",
)
model = VibeVoiceASRForConditionalGeneration.from_pretrained(
    model_id,
    dtype=torch.bfloat16,
    trust_remote_code=True,
).to("cuda")
model.eval()

inputs = processor(
    audio=["audio.wav"],
    sampling_rate=None,
    return_tensors="pt",
    padding=True,
    add_generation_prompt=True,
)
inputs = {
    key: value.to("cuda") if isinstance(value, torch.Tensor) else value
    for key, value in inputs.items()
}
output_ids = model.generate(
    **inputs,
    max_new_tokens=32768,
    pad_token_id=processor.pad_id,
    eos_token_id=processor.tokenizer.eos_token_id,
    do_sample=False,
    num_beams=1,
)
generated_ids = output_ids[0, inputs["input_ids"].shape[1] :]
raw_text = processor.decode(generated_ids, skip_special_tokens=True)
segments = processor.post_process_transcription(raw_text)
```

실험 설정:

- greedy decoding, `max_new_tokens=32768`, context·hotword 미사용
