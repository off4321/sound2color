"""埋め込みベクトルを使った色の類似検索。"""

import numpy as np

from .color import ColorResult
from .db import get_collection


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    2つのベクトルのコサイン類似度を計算する。

    値は -1.0（反対方向）から 1.0（同じ方向）まで。
    """
    vector_a = np.asarray(vec_a)
    vector_b = np.asarray(vec_b)
    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))


def search_colors(
    query_embedding: list[float],
    n_results: int = 5,
) -> list[ColorResult]:
    """
    入力に近い色を ChromaDB から検索する。

    コレクションに設定したコサイン距離（1 - コサイン類似度）を
    類似度に変換して返す。値が大きいほどベクトルが近い。
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"kind": "palette"},
        include=["metadatas", "distances"],
    )
    if not results["ids"] or not results["ids"][0]:
        return []

    color_results: list[ColorResult] = []
    for metadata, distance in zip(
        results["metadatas"][0],
        results["distances"][0],
    ):
        color_results.append(
            ColorResult(
                hex_code=metadata["hex"],
                r=metadata["r"],
                g=metadata["g"],
                b=metadata["b"],
                similarity=1.0 - distance,
            )
        )
    return color_results


def search_audio_colors(
    query_embedding: list[float],
    audio_features: dict[str, float | None],
    n_results: int = 5,
) -> tuple[list[ColorResult], float]:
    """埋め込み順位を保ちつつ、音高・音色に合う明度で再順位付けする。"""
    collection = get_collection()
    total_count = collection.count()
    if total_count == 0:
        return [], 50.0
    palette_count = total_count

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=palette_count,
        where={"kind": "palette"},
        include=["metadatas", "distances"],
    )
    if not results["ids"] or not results["ids"][0]:
        return [], 50.0

    similarities = np.asarray(
        [1.0 - distance for distance in results["distances"][0]],
        dtype=np.float32,
    )
    spectral_centroid = audio_features.get("spectral_centroid_hz")
    if spectral_centroid is None or spectral_centroid <= 0:
        raise ValueError("スペクトル重心を明度調整に利用できません。")
    centroid_lightness = _frequency_to_lightness(
        spectral_centroid,
        low_hz=200,
        high_hz=8_000,
        low_lightness=25,
        high_lightness=85,
    )

    fundamental = audio_features.get("f0_median_hz")
    if fundamental is not None and fundamental > 0:
        pitch_lightness = _frequency_to_lightness(
            fundamental,
            low_hz=55,
            high_hz=1_760,
            low_lightness=30,
            high_lightness=90,
        )
        target_lightness = 0.8 * pitch_lightness + 0.2 * centroid_lightness
    else:
        target_lightness = centroid_lightness

    semantic_order = np.argsort(similarities)[::-1]
    semantic_ranks = np.empty(len(semantic_order), dtype=np.float32)
    semantic_ranks[semantic_order] = np.linspace(
        1.0,
        0.0,
        num=len(semantic_order),
        endpoint=True,
        dtype=np.float32,
    )
    lightness = np.asarray(
        [
            _rgb_lightness(metadata["r"], metadata["g"], metadata["b"])
            for metadata in results["metadatas"][0]
        ],
        dtype=np.float32,
    )
    lightness_match = np.exp(
        -0.5 * ((lightness - target_lightness) / 18.0) ** 2
    )
    ranking_scores = 0.65 * semantic_ranks + 0.35 * lightness_match
    ranked_indices = np.argsort(ranking_scores)[::-1][:n_results]

    color_results = []
    for index in ranked_indices:
        metadata = results["metadatas"][0][int(index)]
        color_results.append(
            ColorResult(
                hex_code=metadata["hex"],
                r=metadata["r"],
                g=metadata["g"],
                b=metadata["b"],
                similarity=float(similarities[index]),
            )
        )
    return color_results, target_lightness


def _frequency_to_lightness(
    frequency_hz: float,
    *,
    low_hz: float,
    high_hz: float,
    low_lightness: float,
    high_lightness: float,
) -> float:
    """周波数を対数尺度で知覚的な明度へ写す。"""
    bounded_frequency = min(max(frequency_hz, low_hz), high_hz)
    proportion = np.log2(bounded_frequency / low_hz) / np.log2(high_hz / low_hz)
    return float(low_lightness + proportion * (high_lightness - low_lightness))


def _rgb_lightness(red: int, green: int, blue: int) -> float:
    """sRGBをCIELABのL*相当値へ変換する。"""
    channels = np.asarray([red, green, blue], dtype=np.float64) / 255
    linear = np.where(
        channels <= 0.04045,
        channels / 12.92,
        ((channels + 0.055) / 1.055) ** 2.4,
    )
    luminance = float(np.dot(linear, [0.2126, 0.7152, 0.0722]))
    delta = 6 / 29
    threshold = delta**3
    lab_y = (
        luminance ** (1 / 3)
        if luminance > threshold
        else luminance / (3 * delta**2) + 4 / 29
    )
    return 116 * lab_y - 16


def get_best_matches(
    query_embedding: list[float],
    top_n: int = 5,
) -> dict:
    """最も近い色と、上位候補をまとめて返す。"""
    matches = search_colors(query_embedding, n_results=top_n)
    if not matches:
        return {
            "best_match": None,
            "all_matches": [],
            "best_hex": None,
            "best_similarity": 0.0,
        }

    return {
        "best_match": matches[0],
        "all_matches": matches,
        "best_hex": matches[0].hex_code,
        "best_similarity": matches[0].similarity,
    }
