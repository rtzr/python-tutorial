# RTZR Streaming STT API (gRPC)

## Requirements
The microphone example requires the `PyAudio` library. Read the [PyAudio installation instructions](https://pypi.org/project/PyAudio/) first.

And Then,

```bash
pip install -r requirements.txt
```
Set the credentials in your environment before running a sample:

```bash
export RTZR_CLIENT_ID=...
export RTZR_CLIENT_SECRET=...
```

Download the official [RTZR streaming proto](https://github.com/rtzr/rtzr-api/blob/main/protos/rtzr-stt.proto) into `src/` and generate the Python client:

```bash
python -m grpc_tools.protoc -I./src --python_out=./src --grpc_python_out=./src ./src/rtzr-stt.proto
```
