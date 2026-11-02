"""
音声・テキスト・画像から色を検索するStreamlitアプリ

入力をEmbeddingGemma 2でベクトル化し、色見本の埋め込みと比較する。
"""

import hashlib
from io import BytesIO

import streamlit as st
from PIL import Image, ImageStat

from lib.color import display_results_streamlit
from lib.db import get_collection, initialize_colors
from lib.embedding import (
    get_audio_embedding_safe,
    get_audio_embedding_with_features_safe,
    get_embedding_safe,
    get_image_embedding_safe,
)
from lib.similarity import get_best_matches, search_audio_colors


# ─── 画面設定 ──────────────────────────────────────────────

st.title("🎨 音や画像から色を探す")
st.caption(
    "音声や説明文をEmbeddingGemma 2でベクトル化し、色見本の単色画像と直接比較します。"
)

# ─── 1. 初期化 ─────────────────────────────────────────────

st.subheader("📦 データ初期化")

# 色見本を ChromaDB に登録する（初回のみ）
color_count = initialize_colors(n_colors=3600)
if color_count is not None:
    st.success(f"色見本 {color_count:,} 色を利用できます。")

# ─── 画像を検索対象として登録 ──────────────────────────────

st.subheader("🖼️ 画像を検索対象として登録")
st.caption("透過部分のある画像は、白背景に合成してから登録します。")
image_uploads = st.file_uploader(
    "画像ファイル（PNG / JPEG / WebP）を選択",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key="image_uploads",
)

if st.button("画像をベクトルDBに登録", disabled=not image_uploads):
    collection = get_collection()
    image_ids: list[str] = []
    image_embeddings: list[list[float]] = []
    image_metadatas: list[dict] = []

    for image_file in image_uploads:
        image_bytes = image_file.getvalue()
        embedding = get_image_embedding_safe(
            image_bytes,
            image_file.name,
            image_file.type or "application/octet-stream",
        )
        if embedding is None:
            break

        with Image.open(BytesIO(image_bytes)) as source_image:
            rgba_image = source_image.convert("RGBA")
            displayed_image = Image.new("RGB", rgba_image.size, "white")
            displayed_image.paste(
                rgba_image,
                mask=rgba_image.getchannel("A"),
            )
            mean_rgb = ImageStat.Stat(displayed_image).mean[:3]
        r, g, b = (round(value) for value in mean_rgb)
        image_ids.append(f"image_{hashlib.sha256(image_bytes).hexdigest()}")
        image_embeddings.append(embedding)
        image_metadatas.append(
            {
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "r": r,
                "g": g,
                "b": b,
                "kind": "image",
                "filename": image_file.name,
            }
        )
    else:
        collection.upsert(
            ids=image_ids,
            embeddings=image_embeddings,
            metadatas=image_metadatas,
        )
        st.success(f"画像 {len(image_ids)} 件を登録しました。")

# ─── 2. 音声データの入力 ───────────────────────────────────

st.subheader("1. 検索する音を入力")

if "audio_upload_version" not in st.session_state:
    st.session_state.audio_upload_version = 0
audio_upload_key = f"audio_upload_{st.session_state.audio_upload_version}"
uploaded_file = st.file_uploader(
    "音声ファイル（WAV / MP3）を選択",
    type=["wav", "mp3"],
    key=audio_upload_key,
)

if uploaded_file:
    st.audio(uploaded_file)
    st.caption("音声全体を加工せず、埋め込みモデルに入力します。")
    if st.button("選択した音声を解除"):
        st.session_state.audio_upload_version += 1
        st.rerun()

sound_description = st.text_input(
    "音声ファイルの代わりに、音の特徴を文章で入力",
    value="硬貨が跳ねる甲高い金属音",
    key="sound_desc_input",
    disabled=uploaded_file is not None,
)

# ─── 3. 色抽出実行 ─────────────────────────────────────────

st.subheader("2. 色を検索")

if st.button("🔮 近い色を探す"):
    if uploaded_file is not None:
        with st.spinner("EmbeddingGemma 2で音声全体を埋め込み中..."):
            audio_representation = get_audio_embedding_with_features_safe(
                uploaded_file.getvalue(),
                uploaded_file.name,
                uploaded_file.type or "application/octet-stream",
            )

        if audio_representation is not None:
            query_vec, audio_features = audio_representation
            results, target_lightness = search_audio_colors(
                query_vec,
                audio_features,
                n_results=5,
            )
            if results:
                st.markdown("---")
                st.success(
                    f"🎯 **{results[0].hex_code}** が最も近い色です "
                    f"(埋め込み類似度: **{results[0].similarity:.2%}**)"
                )
                st.caption(
                    "EmbeddingGemma 2の音声・画像埋め込み順位を、音高と音色から"
                    f"推定した目標明度 L*={target_lightness:.0f} に基づいて調整しています。"
                    f" 検出音高: {audio_features['f0_median_hz'] or '不明'} Hz、"
                    f"スペクトル重心: {audio_features['spectral_centroid_hz']:.0f} Hz。"
                )
                display_results_streamlit(results, top_n=5)
            else:
                st.warning("検索対象の色がありません。色見本の登録状態を確認してください。")
    else:
        target_input = sound_description.strip() or "（テキスト未入力）"
        with st.spinner("EmbeddingGemma 2 で色を検索中..."):
            query_vec = get_embedding_safe(target_input)

        if query_vec is not None:
            matches = get_best_matches(query_vec, top_n=5)

            if matches["best_match"] is not None:
                st.markdown("---")
                st.success(
                    f"🎯 **{matches['best_hex']}** が最も近い色です "
                    f"(埋め込みのコサイン類似度: **{matches['best_similarity']:.2%}**)"
                )

                display_results_streamlit(matches["all_matches"], top_n=5)

            else:
                st.warning("検索対象の色がありません。色見本の登録状態を確認してください。")
