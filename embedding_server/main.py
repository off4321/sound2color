import io
import logging
import os
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

import librosa
import numpy as np
import soundfile
import torch
from audioread.exceptions import NoBackendError
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

MODEL_ID = os.getenv("MODEL_ID", "google/embeddinggemma-2")
MODEL_CACHE_DIR = os.getenv("HF_HOME", "/models")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """起動時にモデルを読み込み、終了時にメモリーを解放する。"""
    dtype = (
        torch.bfloat16
        if DEVICE.type == "cuda" and torch.cuda.is_bf16_supported()
        else torch.float32
    )
    logger.info("Loading model %s on %s", MODEL_ID, DEVICE)
    application.state.model = SentenceTransformer(
        MODEL_ID,
        cache_folder=MODEL_CACHE_DIR,
        device=str(DEVICE),
        model_kwargs={"torch_dtype": dtype},
    )
    application.state.model.eval()
    application.state.inference_lock = Lock()
    logger.info("Model %s loaded", MODEL_ID)
    yield
    application.state.model = None


app = FastAPI(title="マルチモーダル埋め込みサーバー", lifespan=lifespan)


class TextRequest(BaseModel):
    """1件のテキストをベクトル化するリクエスト。"""

    text: str = Field(min_length=1, max_length=32_000)


class TextBatchRequest(BaseModel):
    """複数のテキストをまとめてベクトル化するリクエスト。"""

    texts: list[str] = Field(min_length=1, max_length=32)


def _encode_batch(
    inputs: list[Any],
    *,
    prompt_name: str | None = None,
) -> list[list[float]]:
    """SentenceTransformers公式のプーリング・正規化を通して埋め込む。"""
    model = app.state.model
    with app.state.inference_lock, torch.inference_mode():
        embeddings = model.encode(
            inputs,
            prompt_name=prompt_name,
            batch_size=min(len(inputs), 8),
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings = torch.as_tensor(embeddings).float()
        if embeddings.ndim == 1:
            embeddings = embeddings.unsqueeze(0)

    if embeddings.shape != (len(inputs), 768):
        raise RuntimeError(
            f"Expected embeddings with shape ({len(inputs)}, 768), "
            f"got {tuple(embeddings.shape)}"
        )
    if not bool(torch.isfinite(embeddings).all()):
        raise RuntimeError("Embedding model returned non-finite values")
    return embeddings.cpu().tolist()


def _encode_texts(texts: list[str]) -> list[list[float]]:
    """検索クエリーの文章をモデル指定のSearchQueryタスクで埋め込む。"""
    result: list[list[float]] = []
    for start in range(0, len(texts), 32):
        result.extend(
            _encode_batch(
                texts[start : start + 32],
                prompt_name="SearchQuery",
            )
        )
    return result


@app.get("/healthz")
def healthz():
    """モデルの読み込みが完了しているか確認する。"""
    if getattr(app.state, "model", None) is None:
        raise HTTPException(
            status_code=503,
            detail="埋め込みモデルの読み込みが完了していません。",
        )
    return {"status": "ok", "model": MODEL_ID, "dimensions": 768}


@app.post("/embed/text")
def embed_text(request: TextRequest):
    """テキストを768次元の埋め込みベクトルに変換する。"""
    embedding = _encode_batch(
        [request.text],
        prompt_name="SearchQuery",
    )
    return {"embedding": embedding[0], "dimensions": 768}


@app.post("/embed/texts")
def embed_texts(request: TextBatchRequest):
    """複数のテキストをまとめてベクトル化する。"""
    return {
        "embeddings": _encode_texts(request.texts),
        "dimensions": 768,
    }


@app.post("/embed/image")
def embed_image(file: UploadFile = File(...)):
    """画像を768次元の埋め込みベクトルに変換する。"""
    contents = file.file.read()
    try:
        with Image.open(io.BytesIO(contents)) as source_image:
            rgba_image = source_image.convert("RGBA")
            image = Image.new("RGB", rgba_image.size, "white")
            image.paste(rgba_image, mask=rgba_image.getchannel("A"))
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400,
            detail="画像を読み込めませんでした。対応形式の画像を指定してください。",
        ) from error

    embeddings = _encode_batch([{"text": "<|image|>", "image": image}])
    return {"embedding": embeddings[0], "dimensions": 768}


@app.post("/embed/images")
def embed_images(files: list[UploadFile] = File(...)):
    """複数の画像をまとめて768次元の埋め込みベクトルに変換する。"""
    if not files or len(files) > 16:
        raise HTTPException(
            status_code=400,
            detail="一度に処理できる画像は1〜16枚です。",
        )

    images: list[Image.Image] = []
    for file in files:
        try:
            with Image.open(io.BytesIO(file.file.read())) as source_image:
                rgba_image = source_image.convert("RGBA")
                image = Image.new("RGB", rgba_image.size, "white")
                image.paste(rgba_image, mask=rgba_image.getchannel("A"))
                images.append(image)
        except (UnidentifiedImageError, OSError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"画像を読み込めませんでした: {file.filename}",
            ) from error

    model_inputs = [
        {"text": "<|image|>", "image": image}
        for image in images
    ]
    return {"embeddings": _encode_batch(model_inputs), "dimensions": 768}


@app.post("/embed/audio")
def embed_audio(file: UploadFile = File(...)):
    """音声を16kHz・モノラルに変換してベクトル化する。"""
    audio = _load_audio(file.file.read())
    embeddings = _encode_batch([{"text": "<|audio|>", "audio": audio}])
    return {
        "embedding": embeddings[0],
        "audio_features": _extract_audio_features(audio),
        "dimensions": 768,
    }


def _extract_audio_features(audio: np.ndarray) -> dict[str, float | None]:
    """音高と音色の明るさに関わる特徴を解析する。"""
    frame_length = 2048
    hop_length = 512
    padded_audio = np.pad(
        audio,
        (0, max(0, frame_length - len(audio))),
    )
    rms = librosa.feature.rms(
        y=padded_audio,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]
    active_frames = rms >= max(float(rms.max()) * 0.1, 1e-6)
    if not bool(active_frames.any()):
        raise ValueError("音声から有効な音響特徴を抽出できません。")

    centroids = librosa.feature.spectral_centroid(
        y=padded_audio,
        sr=16_000,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]
    flatness = librosa.feature.spectral_flatness(
        y=padded_audio,
        n_fft=frame_length,
        hop_length=hop_length,
    )[0]
    spectral_centroid_hz = float(np.median(centroids[active_frames]))
    spectral_flatness = float(np.median(flatness[active_frames]))

    f0_median_hz: float | None = None
    if spectral_flatness < 0.3:
        pitches = librosa.yin(
            padded_audio,
            fmin=55,
            fmax=1_760,
            sr=16_000,
            frame_length=frame_length,
            hop_length=hop_length,
        )
        voiced_frames = active_frames[: len(pitches)]
        if bool(voiced_frames.any()):
            f0_median_hz = float(np.median(pitches[voiced_frames]))

    return {
        "f0_median_hz": f0_median_hz,
        "spectral_centroid_hz": spectral_centroid_hz,
        "spectral_flatness": spectral_flatness,
        "rms_db": float(20 * np.log10(max(float(rms[active_frames].mean()), 1e-8))),
    }


def _load_audio(contents: bytes) -> np.ndarray:
    """音声データを16kHz・モノラルで読み込む。"""
    if not contents:
        raise HTTPException(status_code=400, detail="音声ファイルが空です。")

    try:
        audio, _ = librosa.load(
            io.BytesIO(contents),
            sr=16_000,
            mono=True,
        )
    except (
        NoBackendError,
        soundfile.LibsndfileError,
        ValueError,
        RuntimeError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail="音声ファイルを読み込めません。対応形式の音声を指定してください。",
        ) from error

    if not np.isfinite(audio).all():
        raise HTTPException(
            status_code=400,
            detail="音声データに不正な値が含まれています。",
        )
    return audio
