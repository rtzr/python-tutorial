import time
from pathlib import Path

import streamlit as st
from model import RtzrAPI
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast


@st.cache_resource()  # cache사용해서 새로고침 시 리소스 절감
def load_model():
    """모델 불러오는 함수"""
    model = BartForConditionalGeneration.from_pretrained("EbanLee/kobart-summary-v3")
    tokenizer = PreTrainedTokenizerFast.from_pretrained("EbanLee/kobart-summary-v3")
    return model, tokenizer


def stream_data(text: str) -> None:
    """인자로 받은 text를 출력해주는 함수"""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)


def file_upload_save(dir: str, upload_file: str) -> Path:
    """업로드한 파일을 지정된 경로에 다운받고, 로컬 폴더의 경로를 반환하는 함수"""
    if upload_file is None:
        raise ValueError("An audio file is required")
    target_dir = Path(dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / Path(upload_file.name).name
    path.write_bytes(upload_file.read())
    return path


def display_audio_file(wavpath: str) -> None:
    """streamlit audio 재생"""
    audio_bytes = Path(wavpath).read_bytes()
    file_type = Path(wavpath).suffix.lstrip(".")
    st.audio(audio_bytes, format=f"audio/{file_type}", start_time=0)


def page_setup(logo_url: str, homepage_url: str, tutorial_url: str) -> st.file_uploader:
    """streamlit 메인페이지 구성 return은 음성 파일이 들어있는 my_upload"""

    if "model" not in st.session_state:
        with st.spinner("model and page loading..."):
            st.session_state.model, st.session_state.tokenizer = load_model()

    st.markdown(
        f'[![Click me]({logo_url})]({homepage_url}) <span style="font-size: 30px;">**Return Zero**</span>',
        unsafe_allow_html=True,
    )
    st.header("음성 변환 및 요약 웹앱 Tutorial", divider="gray")

    st.subheader("[API 키 발급 받으러 가기](%s)" % tutorial_url)
    st.sidebar.write("## 아래를 채워주세요!(*는 필수)")
    with st.sidebar.form("my-form", clear_on_submit=False):
        st.text_input("*Client Id를 작성해주세요👇", placeholder="client id", key="client_id")
        st.text_input(
            "*Client Secret을 작성해주세요👇",
            placeholder="client secret",
            key="client_secret",
        )
        my_upload = st.file_uploader(
            "*오디오 파일을 업로드 해주세요",
            type=["mp4", "m4a", "mp3", "amr", "flac", "wav"],
            key="file",
        )
        st.radio("화자의 수는 몇 명인가요?", ["1", "2", "3", "4+"], key="speaker_num")
        st.radio("도메인은 어떤 분야인가요?", ["일반", "전화통화"], key="domain")
        st.checkbox("욕설 필터링을 할까요?", key="profanity_filter")
        st.text_input(
            "음성 인식에 중요한 키워드를 입력해주세요",
            placeholder="대한민국, 일본, 중국",
            key="boost_keyword",
        )
        st.form_submit_button("submit")
    return my_upload


def display_result(audio_file_path: str, upload_file: st.file_uploader) -> None:
    """streamlit 결과 화면"""
    if st.session_state.client_id and st.session_state.client_secret and st.session_state.file:
        file_path = None
        try:
            file_path = file_upload_save(audio_file_path, upload_file)
            speaker_num = 0 if st.session_state.speaker_num == "4+" else int(st.session_state.speaker_num)
            with file_path.open("rb") as audio_file:
                api = RtzrAPI(
                    st.session_state.client_id,
                    st.session_state.client_secret,
                    {"file": (file_path.name, audio_file)},
                    speaker_num,
                    st.session_state.domain,
                    st.session_state.profanity_filter,
                    st.session_state.boost_keyword.replace(" ", "").split(","),
                    st.session_state.model,
                    st.session_state.tokenizer,
                )

                with st.spinner("wait for it"):
                    api.wait_for_result()

                    # inference
                    api.summary_inference()

                    # audio file display
                    display_audio_file(str(file_path))

                    # result print
                    col1, col2 = st.columns(2)
                    col1.markdown("## 음성 변환")
                    all_text_field = col1.container(border=True, height=400)

                    col2.markdown("## 음성 변환 요약")
                    summary_text_field = col2.container(border=True, height=400)

                    all_text_field.write_stream(stream_data(api.get_text_data()))
                    summary_text_field.write_stream(stream_data(api.get_summary_data()))

        except Exception as e:
            st.error(f"오류 발생: {e}")
        finally:
            if file_path is not None:
                file_path.unlink(missing_ok=True)

    else:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("Client id, Client Secret, 변환할 파일을 올려주세요")
