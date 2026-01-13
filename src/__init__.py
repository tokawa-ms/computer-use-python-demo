"""
computer-use-test パッケージ

Azure OpenAI の computer-use 機能を使用してWindows環境を自動操作するためのパッケージです。

モジュール構成:
- config: 環境設定と定数の管理
- utils: 汎用ユーティリティ関数
- client: Azure OpenAI クライアントとAPI通信
- image_processing: スクリーンショットと画像処理
- actions: コンピューター操作の実行
- session: セッション管理とログ記録
- confirmation: ユーザー確認の自動化
- debug: デバッグ情報の生成
- main: メイン実行ロジック
"""

__version__ = "1.0.0"

from . import actions
from . import client
from . import config
from . import confirmation
from . import debug
from . import image_processing
from . import main
from . import session
from . import utils

__all__ = [
    "actions",
    "client",
    "config",
    "confirmation",
    "debug",
    "image_processing",
    "main",
    "session",
    "utils",
]
