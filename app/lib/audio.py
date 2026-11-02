"""音声ファイルの一時保存・再生を補助する関数。"""

import os
import shutil
import tempfile
import uuid

import streamlit as st

AUDIO_DIR = os.path.join(tempfile.gettempdir(), "audio")
ALLOWED_EXTENSIONS = (".wav", ".mp3")


def ensure_audio_dir() -> None:
    """一時保存用のフォルダーを作成する。"""
    os.makedirs(AUDIO_DIR, exist_ok=True)


def save_upload(file_obj, original_name: str | None = None) -> str:
    """
    Streamlit で受け取った音声を一時保存する。

    Returns:
        保存先の絶対パス。
    """
    ensure_audio_dir()
    extension = os.path.splitext(file_obj.name)[1]
    name = original_name or f"{uuid.uuid4().hex}{extension}"
    safe_name = "".join(char for char in name if char.isalnum() or char in "._-")
    safe_name = safe_name[:80] or f"audio_{uuid.uuid4().hex[:8]}"

    file_path = os.path.join(AUDIO_DIR, safe_name)
    file_obj.seek(0)
    with open(file_path, "wb") as saved_file:
        shutil.copyfileobj(file_obj, saved_file)
    return file_path


def delete_audio(file_path: str) -> bool:
    """一時保存した音声を削除する。"""
    if not os.path.exists(file_path):
        return False
    os.remove(file_path)
    return True


def play_audio(file_path: str) -> None:
    """一時保存した音声を画面上で再生する。"""
    if not os.path.exists(file_path):
        st.error(f"音声ファイルが見つかりません: {file_path}")
        return
    st.audio_file(file_path)


def get_audio_path(file_path: str) -> str:
    """音声ファイルの絶対パスを返す。"""
    return os.path.abspath(file_path)


def list_audio_files() -> list[str]:
    """一時保存フォルダーにある WAV / MP3 ファイルを列挙する。"""
    if not os.path.exists(AUDIO_DIR):
        return []
    return [
        os.path.join(AUDIO_DIR, file_name)
        for file_name in os.listdir(AUDIO_DIR)
        if file_name.lower().endswith(ALLOWED_EXTENSIONS)
    ]
