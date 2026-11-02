"""
音声 → 色の人工共感覚ビジュアライザーの共通機能。

- embedding: multimodal embedding server API 呼び出し
- db: ChromaDB 接続と色データ初期化
- color: カラーコード生成と表示
- audio: 音声ファイルの取得・削除・再生
- similarity: 類似検索結果の整形
"""
