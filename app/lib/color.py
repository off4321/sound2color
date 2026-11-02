"""色検索結果を画面表示用に整える。"""

from dataclasses import dataclass


@dataclass
class ColorResult:
    """検索で見つかった色と、その色に対応するベクトル距離。"""

    hex_code: str
    r: int
    g: int
    b: int
    similarity: float


def generate_color_box_html(hex_code: str, similarity: float = 1.0) -> str:
    """色コードとコサイン類似度を示す HTML を生成する。"""
    r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
    brightness = (r + g + b) / 3
    text_color = "black" if brightness > 128 else "white"

    return f"""
    <div style="
        width: 100%;
        height: 120px;
        background-color: {hex_code};
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        color: {text_color};
        font-size: 20px;
        font-weight: bold;
        text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
    ">
        {hex_code}<br><small>コサイン類似度: {similarity:.2%}</small>
    </div>
    """


def format_results(results: list[ColorResult], top_n: int = 5) -> str:
    """検索結果を Markdown の表にする。"""
    if not results:
        return "検索結果がありません。"

    rows = []
    for rank, result in enumerate(results[:top_n], 1):
        rank_symbol = (
            "🥇" if rank == 1 else
            "🥈" if rank == 2 else
            "🥉" if rank == 3 else
            f"#{rank}"
        )
        rows.append(
            f"| {rank_symbol} | `{result.hex_code}` | {result.similarity:.2%} |"
        )

    lines = [
        "| 順位 | カラーコード | コサイン類似度 |",
        "|:---:|:---:|:---:|",
        *rows,
    ]
    return "\n".join(lines)


def display_results_streamlit(
    results: list[ColorResult],
    top_n: int = 5,
) -> None:
    """検索結果を Streamlit に表示する。"""
    import streamlit as st

    st.subheader(f"🎨 類似した色（上位 {min(len(results), top_n)} 件）")
    for rank, result in enumerate(results[:top_n], 1):
        rank_symbol = (
            "🥇" if rank == 1 else
            "🥈" if rank == 2 else
            "🥉" if rank == 3 else
            f"#{rank}"
        )
        st.markdown(
            f"**{rank_symbol} {result.hex_code}** "
            f"— コサイン類似度: {result.similarity:.2%}"
        )
        st.markdown(
            format_color_box_inline(result.hex_code, result.similarity),
            unsafe_allow_html=True,
        )
    st.markdown(format_results(results, top_n))


def format_color_box_inline(hex_code: str, similarity: float = 1.0) -> str:
    """画面に表示する小さな色見本の HTML を生成する。"""
    r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
    brightness = (r + g + b) / 3
    text_color = "black" if brightness > 128 else "white"

    return f"""
    <div style="
        width: 60px;
        height: 60px;
        background-color: {hex_code};
        border-radius: 8px;
        margin: 8px 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: {text_color};
        font-size: 14px;
        font-weight: bold;
    ">
        {hex_code[-4:]}
    </div>
    """
