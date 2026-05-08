FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip git \
    libgl1-mesa-glx libglib2.0-0 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && pip install --upgrade pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "torch==2.4.1" "torchvision==0.19.1" --index-url https://download.pytorch.org/whl/cu124

RUN pip install --no-cache-dir \
    "diffusers>=0.30.0" \
    "transformers>=4.43.0" \
    "accelerate>=0.33.0" \
    "sentencepiece" \
    "protobuf" \
    "safetensors" \
    "Pillow" \
    "fastapi" \
    "uvicorn[standard]" \
    "pydantic>=2.0" \
    "huggingface_hub[hf_transfer]"

WORKDIR /app
COPY server.py .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
