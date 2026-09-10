# Python Audio Processing Tutorials

Welcome to the Python Audio Processing Tutorials repository. This repository contains examples for real-time audio processing with RTZR APIs and related tools.

## Disclaimer

This repository contains educational examples only. Accuracy, completeness, freshness, API compatibility, and production quality are not guaranteed. Verify the current [RTZR Developers documentation](https://developers.rtzr.ai/docs/) and test the examples in your own environment before production use.

## Projects

### 1. RTZR Streaming STT API(gRPC) with Mic. Interface

This project demonstrates how to set up a real-time streaming Speech-to-Text (STT) API using gRPC with microphone interface capabilities. It requires the installation of the `PyAudio` library and additional setup for gRPC communication.

- **Requirements**: PyAudio (see [installation instructions](https://pypi.org/project/PyAudio/)).
- **Setup**: Download necessary `.proto` files and generate gRPC client code. For details, check the project's [README](./python-stt-sample/).

### 2. Triton, Tritony VAD Client Sample

This project showcases the use of the Triton Inference Server and Tritony Voice Activity Detection (VAD) to process and analyze audio streams effectively. It involves setting up a Docker container and running a Triton server.

- **Requirements**: pydub, tritonclient, tritony
- **Setup**: Build and run a Docker image for the Triton Inference Server. Testing is facilitated through predefined scripts and pytest. For more information, visit the project's [README](./tritony-sample/).

### 3. STT and STT summary WEBAPP with Python streamlit

Implementation of a web app using only Python's Streamlit and Return Zero's API, without knowledge of frontend and backend development. This web app include functionality to convert audio files to text using Return Zero's API for Speech-to-Text (STT), and then summarizes the converted text.

- **Requirements**: streamlit, requests, pytorch, transformers
- **Setup**: Install requirement librarys, Run streamlit and submit your information. For more information, visit the project's [README](./streamlit-webapp/).

### 4. RTZR Batch STT Refinement & Insight CLI

This project provides a Python CLI for transcribing local audio files with the RTZR Batch STT API. It supports speaker diarization by default and can optionally refine transcripts or generate Korean insights.

- **Requirements**: Python 3.10+, `uv`
- **Enterprise features**: Transcript refinement and insight generation require prior access approval.
- **Setup and usage**: See the [project README](./stt-refinement-insight/).

## Installation

Each project has its own dependencies and setup instructions. Follow the README in the project directory you want to run.
