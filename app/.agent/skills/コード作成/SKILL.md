---
name: コード作成
description: 高品質なコードを作成するスキル。コメントは日本語で記載し、可読性が高く保守性のよいコードを生み出します。プロジェクトのコーディング規約に準拠し、ベストプラクティスを遵循した実装を行います。
---

# コード作成スキル

このスキルは、分かりやすく保守性の高いコードを生成するためのガイドラインを提供します。特に日本語コメントの活用、可読性の向上、および長期的な保守性を重視した実装を心がけます。

## 基本的な原則

### 1. 日本語コメントの活用

 comments はコードを理解するための重要な補助情報です。以下の特徴を持つコメントを記述しましょう：

- **説明的コメント**: 「なぜ」そのような実装をしたのかを説明
- **警告コメント**: 注意すべき点、将来の変更が必要そうな箇所に注釈
- **要約コメント**: 複雑なロジックの冒頭に簡潔な要約

```javascript
/**
 * ユーザーの認証情報を検証する関数
 * 
 * @param {string} token - 認証トークン
 * @param {string} userId - ユーザーID
 * @returns {boolean} 認証が成功したか
 * 
 * 注意: トークンの有効期限切れは30秒以内で再認証を促す
 */
function validateAuth(token, userId) {
    // FIXME: 2024年末までにOAuth2.0への移行を検討
    // 現在の実装は簡易的なハッシュ検証のみ
    const isValid = simpleValidate(token);
    
    if (!isValid) {
        logWarning(`認証失敗: トークン無効`, userId);
    }
    
    return isValid;
}
```

### 2. 可読性の高いコード

コード自体が自己文書化されるように努めましょう：

#### 変数・関数名
- **意味を持つ名称**: `data` ではなく `userData`, `result` ではなく `validatedResult`
- **動詞 + 名前の形式**: `getUserData()`, `validateInput()`, `processPayment()`
- **否定は避ける**: `isNotValid` ではなく `isValid`（条件分岐で調整）

#### 構造的なパターン
- **適切な長さ**: 関数は10-20行程度を心がける
- **明示的な条件分岐**: 不必要なネストを避ける
- **早期リターン**: エラーハンドリングを早期リターンで整理

```python
# 可読性を向上させた例
def process_user_payment(payment_request):
    """
    決済リクエストを処理する
    
    Args:
        payment_request: 決済リクエストオブジェクト
        
    Returns:
        bool: 処理成功かどうか
        
    Raises:
        InvalidRequestError: 無効なリクエストの場合
        PaymentFailedError: 決済処理に失敗した場合
    """
    # 1. リクエストのバリデーション
    if not validate_request(payment_request):
        raise InvalidRequestError("無効なリクエストです")
    
    # 2. ユーザーの存在確認
    user = get_user(payment_request.user_id)
    if not user:
        raise UserNotFoundError(f"ユーザー {payment_request.user_id} が見つかりません")
    
    # 3. 支払い処理
    try:
        result = process_payment(user, payment_request.amount)
    except PaymentFailedError as e:
        logger.error(f"支払い処理に失敗: {e}")
        raise
        
    return result.success
```

### 3. 保守性の高い実装

未来の変化を見据えた設計を心がけましょう：

#### DRY 原則 (Don't Repeat Yourself)
重複するコードは共通化・抽象化しましょう。

#### ソロロゲインの原則 (SRP)
1つの関数・クラスは1つの責任のみを持つ。

#### 依存性の注射
外部依存を注入可能にし、テスト容易性を高める。

#### 魔法の数値の排除
ハードコードされた数値は定数化し、意味のある名前をつける。

## コーディング規約遵守

プロジェクトのコーディング規約に従うことを必ず確認してください：

- **インデント**: 4 スペース慣習（またはプロジェクト規定）
- **行長**: 最大80-100文字（読みやすさを優先）
- **空行**: 関連するコードブロック間の可読性確保
- **ファイル構造**: 機能ごとのモジュール分割

## ラベルと定数

明確なラベルと定数はコードの理解を深めます：

```python
# 魔法の数値の排除例
# 悪い例
if status == 200:
    return True

# 良い例
HTTP_SUCCESS_STATUS = 200

if status == HTTP_SUCCESS_STATUS:
    return True
```

## 構文と文脈に応じた実装

### クラス設計
```python
class PaymentProcessor:
    """
    決済処理を管理するクラス
    
    特徴:
    - 支払い方法ごとのバリアントを拡張可能
    - ロギングとエラーハンドリング内蔵
    - トランザクション管理サポート
    """
    
    def __init__(self, payment_gateway):
        self.payment_gateway = payment_gateway
        self.logger = Logger.get_logger(__name__)
    
    def process(self, amount, user_id):
        """
        決済処理を実行
        
        Args:
            amount: 処理金額
            user_id: ユーザーID
            
        Returns:
            PaymentResult: 処理結果
            
        Raises:
            PaymentError: 処理に失敗した場合
        """
        # 実装
        pass
```

### 関数型プログラミングのアプローチ
必要に応じて、不変性を保ちつつ純粋関数を利用する。

## 例示パターン

### 実装例：ユーザー登録処理

```python
def register_user(user_data):
    """
    新しいユーザーを登録する
    
    Args:
        user_data (dict): ユーザー情報辞書
            必須: username, email, password
            任意: first_name, last_name, phone
            
    Returns:
        User: 作成されたユーザーオブジェクト
            
    Raises:
        RegistrationError: ユーザー登録に失敗した場合
            
    備考:
    - パスワードは塩付きハッシュ化される
    - 重複チェックはデータベースレベルで実行
    - メール認証はバックグラウンドで非同期処理
    """
    
    try:
        # 1. 必須項目のバリデーション
        required_fields = ['username', 'email', 'password']
        missing = [field for field in required_fields if field not in user_data]
        if missing:
            raise RegistrationError(f"必須項目が不足しています: {', '.join(missing)}")
        
        # 2. 形式バリデーション
        if not validate_email_format(user_data['email']):
            raise RegistrationError("無効なメールアドレス形式です")
        
        # 3. パスワード強度チェック
        if not check_password_strength(user_data['password']):
            raise RegistrationError("パスワードが弱すぎます")
        
        # 4. 重複チェック
        existing = User.query.filter(
            (User.username == user_data['username']) |
            (User.email == user_data['email'])
        ).first()
        
        if existing:
            raise RegistrationError("既に存在するユーザー名またはメールアドレスです")
        
        # 5. パスワードハッシュ化
        hashed_password = hash_password(user_data['password'])
        
        # 6. ユーザー作成
        new_user = User(
            username=user_data['username'],
            email=user_data['email'],
            password=hashed_password,
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            phone=user_data.get('phone')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # 7. 非同期処理: 認証メール送信
        send_verification_email.delay(new_user.id, new_user.email)
        
        return new_user
        
    except RegistrationError:
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"ユーザー登録エラー: {str(e)}")
        raise RegistrationError("ユーザー登録に失敗しました")
```

## レビューポイント

コードを作成する際は、以下の観点から自己レビューを行ってください：

- [ ] 日本語コメントが適切か
- [ ] 変数・関数名に意味があるか
- [ ] 関数の長さと複雑性が適切か
- [ ] エラーハンドリングが網羅されているか
- [ ] ドキュメントが必要か
- [ ] 一貫したスタイルが保たれているか
- [ ] 将来の変更が容易か
- [ ] 規約に従っているか

## まとめ

このスキルを使用して生成されるコードは、以下の品質基準を満たすことを目指します：

1. **明確な意図**: コメントと命名でコードの意図が明確
2. **高い可読性**: 誰でも簡単に理解できる構造
3. **拡張性**: 将来の変更に柔軟に対応可能
4. **保守性**: 長期的に維持・改良しやすい

コード作成では、単に動くものを作るだけでなく、将来の自分や他の開発者にとって使いやすいコードを書くことを心がけてください。
