"""
ChromaDB 接続と色パレットの初期化モジュール

埋め込みベクトルを ChromaDB に格納し、
類似検索を行うための基盤を提供する。
"""

import os
from io import BytesIO

from chromadb import Collection, HttpClient
from PIL import Image
import streamlit as st

_CHROMA_HOST = os.getenv("CHROMA_HOST", "vector-db")
_CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "color_synesthesia_embeddinggemma2_official_v1"


def get_chroma_client() -> HttpClient:
    """ChromaDB の HTTP クライアントを作成する。"""
    return HttpClient(host=_CHROMA_HOST, port=_CHROMA_PORT)


def get_collection() -> Collection:
    """EmbeddingGemma 2 用のコレクションを取得または作成する。"""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _factor_into_three(n: int) -> tuple[int, int, int]:
    """n をできるだけ均等な3因子に分解する。"""
    a = 1
    for i in range(int(n ** (1 / 3)) + 2, 0, -1):
        if n % i == 0:
            a = i
            break
    remaining = n // a
    b = 1
    for j in range(int(remaining ** (1 / 2)) + 2, 0, -1):
        if remaining % j == 0:
            b = j
            break
    return a, b, remaining // b


def _evenly_spaced_values(n: int, max_val: int = 255) -> list[int]:
    """0 から max_val までを n 個に等間隔で分割する。"""
    if n == 1:
        return [0]
    return [int(round(i * max_val / (n - 1))) for i in range(n)]


def initialize_colors(n_colors: int = 3600) -> int | None:
    """単色画像を公式埋め込み経路で登録し、途中失敗時は次回に再開する。"""
    from .embedding import get_image_embeddings_safe

    collection = get_collection()
    n_r, n_g, n_b = _factor_into_three(n_colors)
    total_colors = n_r * n_g * n_b
    r_values = _evenly_spaced_values(n_r)
    g_values = _evenly_spaced_values(n_g)
    b_values = _evenly_spaced_values(n_b)

    palette: list[tuple[str, tuple[int, int, int]]] = []
    for r in r_values:
        for g in g_values:
            for b in b_values:
                hex_code = f"#{r:02x}{g:02x}{b:02x}"
                palette.append((hex_code, (r, g, b)))

    existing_ids = set(
        collection.get(where={"kind": "palette"}, include=[])["ids"]
    )
    desired_ids = {f"color_{index:04d}" for index in range(len(palette))}
    stale_ids = existing_ids - desired_ids
    if stale_ids:
        collection.delete(ids=list(stale_ids))
    missing_colors = [
        index
        for index in range(len(palette))
        if f"color_{index:04d}" not in existing_ids
    ]
    if not missing_colors:
        return len(palette)

    st.info(f"色見本を公式埋め込み経路で登録しています（{len(palette):,}色）。")
    st.write(
        f"RGB の組み合わせ: {n_r} × {n_g} × {n_b} = {total_colors:,}色。"
        "各色を単色画像として登録し、音声全体の埋め込みと直接比較します。"
    )
    progress = st.progress(0)
    batch_size = 8
    for start in range(0, len(missing_colors), batch_size):
        batch_indices = missing_colors[start : start + batch_size]
        image_files: list[tuple[str, bytes, str]] = []
        metadatas: list[dict] = []
        ids: list[str] = []
        for index in batch_indices:
            hex_code, (r, g, b) = palette[index]
            image_buffer = BytesIO()
            Image.new("RGB", (224, 224), (r, g, b)).save(
                image_buffer,
                format="PNG",
            )
            image_files.append(
                (
                    f"{hex_code[1:]}.png",
                    image_buffer.getvalue(),
                    "image/png",
                )
            )
            ids.append(f"color_{index:04d}")
            metadatas.append(
                {
                    "hex": hex_code,
                    "r": r,
                    "g": g,
                    "b": b,
                    "kind": "palette",
                }
            )

        embeddings = get_image_embeddings_safe(image_files)
        if embeddings is None:
            progress.empty()
            return None
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
        progress.progress(
            min(start + len(batch_indices), len(missing_colors)) / len(missing_colors)
        )

    progress.empty()
    st.success(
        f"{len(palette):,}色を各1件の画像埋め込みで登録しました。"
    )
    return len(palette)
