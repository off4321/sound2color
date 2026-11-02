"""埋め込みサーバーに画像・音声・テキストを送り、ベクトルを受け取る。"""

import math
import os

import requests
import streamlit as st

_BASE_URL = os.getenv(
    "EMBEDDING_SERVER_URL",
    "http://multimodal-embedding-server:8000",
).rstrip("/")
REQUEST_TIMEOUT = 300
EMBEDDING_DIMENSIONS = 768


def _request_embedding(
    route: str,
    *,
    json: dict | None = None,
    files: dict | list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> dict | None:
    """埋め込みサーバーを呼び出す。失敗時は画面に理由を表示する。"""
    try:
        response = requests.post(
            f"{_BASE_URL}{route}",
            json=json,
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.ConnectionError as error:
        st.error(f"埋め込みサーバーに接続できません。接続先を確認してください。\n\n{error}")
        return None
    except requests.Timeout as error:
        st.error(f"埋め込みサーバーの応答がタイムアウトしました。\n\n{error}")
        return None
    except requests.HTTPError as error:
        detail = error.response.text if error.response is not None else str(error)
        st.error(f"埋め込み処理に失敗しました。\n\n{detail}")
        return None

    try:
        payload = response.json()
    except ValueError as error:
        st.error(f"埋め込みサーバーから正しい形式の応答がありません。\n\n{error}")
        return None

    if not isinstance(payload, dict):
        st.error("埋め込みサーバーの応答形式が正しくありません。")
        return None
    return payload


def _parse_embedding(payload: dict) -> list[float] | None:
    """応答に768個の数値が含まれることを確認する。"""
    embedding = payload.get("embedding")
    if (
        not isinstance(embedding, list)
        or len(embedding) != EMBEDDING_DIMENSIONS
        or any(not isinstance(value, (int, float)) for value in embedding)
    ):
        st.error(
            "埋め込みサーバーから768次元のベクトルを取得できませんでした。"
        )
        return None
    return [float(value) for value in embedding]


def get_embedding_safe(text: str) -> list[float] | None:
    """テキストを送り、768次元のベクトルを取得する。"""
    payload = _request_embedding("/embed/text", json={"text": text})
    return _parse_embedding(payload) if payload is not None else None


def get_embeddings_safe(texts: list[str]) -> list[list[float]] | None:
    """複数のテキストをまとめて送り、それぞれのベクトルを取得する。"""
    payload = _request_embedding("/embed/texts", json={"texts": texts})
    if payload is None:
        return None

    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        st.error("埋め込みサーバーから正しい件数のベクトルが返りませんでした。")
        return None

    parsed: list[list[float]] = []
    for embedding in embeddings:
        vector = _parse_embedding({"embedding": embedding})
        if vector is None:
            return None
        parsed.append(vector)
    return parsed


def get_image_embedding_safe(
    image: bytes,
    filename: str,
    content_type: str,
) -> list[float] | None:
    """画像データを送り、768次元のベクトルを取得する。"""
    payload = _request_embedding(
        "/embed/image",
        files={"file": (filename, image, content_type)},
    )
    return _parse_embedding(payload) if payload is not None else None


def get_image_embeddings_safe(
    images: list[tuple[str, bytes, str]],
) -> list[list[float]] | None:
    """画像をまとめて送り、それぞれの768次元ベクトルを取得する。"""
    payload = _request_embedding(
        "/embed/images",
        files=[
            ("files", (filename, image, content_type))
            for filename, image, content_type in images
        ],
    )
    if payload is None:
        return None

    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(images):
        st.error("埋め込みサーバーから正しい件数のベクトルが返りませんでした。")
        return None

    parsed: list[list[float]] = []
    for embedding in embeddings:
        vector = _parse_embedding({"embedding": embedding})
        if vector is None:
            return None
        parsed.append(vector)
    return parsed


def get_audio_embedding_safe(
    audio: bytes,
    filename: str,
    content_type: str,
) -> list[float] | None:
    """音声データを送り、768次元のベクトルを取得する。"""
    payload = _request_embedding(
        "/embed/audio",
        files={"file": (filename, audio, content_type)},
    )
    return _parse_embedding(payload) if payload is not None else None


def get_audio_embedding_with_features_safe(
    audio: bytes,
    filename: str,
    content_type: str,
) -> tuple[list[float], dict[str, float | None]] | None:
    """音声埋め込みと、明度調整に使う音響特徴を取得する。"""
    payload = _request_embedding(
        "/embed/audio",
        files={"file": (filename, audio, content_type)},
    )
    if payload is None:
        return None

    embedding = _parse_embedding(payload)
    if embedding is None:
        return None
    features = payload.get("audio_features")
    if not isinstance(features, dict):
        st.error("埋め込みサーバーから音響特徴を取得できませんでした。")
        return None

    parsed_features: dict[str, float | None] = {}
    for name in (
        "f0_median_hz",
        "spectral_centroid_hz",
        "spectral_flatness",
        "rms_db",
    ):
        value = features.get(name)
        if value is None and name == "f0_median_hz":
            parsed_features[name] = None
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            st.error(f"音響特徴「{name}」の形式が正しくありません。")
            return None
        parsed_features[name] = float(value)

    return embedding, parsed_features
