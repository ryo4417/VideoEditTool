"""組み込みプラグインの登録。

import した時点で、デコレータによりレジストリへ登録される。
将来的にはここで外部プラグインディレクトリの走査を追加できる（拡張点）。
"""
# import 副作用でレジストリに登録される。
from audio import silence as _silence  # noqa: F401
from audio import speech as _speech  # noqa: F401
from audio import transcript as _transcript  # noqa: F401
from rules import filler_rule as _filler_rule  # noqa: F401
from rules import silence_rule as _silence_rule  # noqa: F401


def load_builtins() -> None:
    """組み込みアナライザ／ルールを登録済みにする明示的エントリ。"""
    # 上の import 時点で登録済み。呼び出し側の意図を明確にするための関数。
    return None
