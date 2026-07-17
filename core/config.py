"""設定システム。

編集条件は全て設定ファイル（YAML）で管理する（仕様書 §7）。
default.yaml をベースに、案件プロファイルを深いマージで上書きする。
コードを書き換えずに ON/OFF・閾値変更・ルール追加ができる。
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# リポジトリ直下（core/ の親）を基準にする。ハードコードした絶対パスは持たない。
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _ROOT / "config"
_DEFAULT = _CONFIG_DIR / "default.yaml"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """override を base に深くマージした新しい辞書を返す。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """ドット記法で読める設定オブジェクト。"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get(self, path: str, default: Any = None) -> Any:
        """'rules.silence.min_cut_sec' のようなドット区切りで取得。"""
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, path: str) -> Dict[str, Any]:
        value = self.get(path, {})
        return value if isinstance(value, dict) else {}

    @property
    def data(self) -> Dict[str, Any]:
        return self._data


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(profile: Optional[str] = None) -> Config:
    """default.yaml を読み、profile 指定時は config/profiles/<profile>.yaml で上書き。"""
    data = _load_yaml(_DEFAULT)
    if profile:
        profile_path = _CONFIG_DIR / "profiles" / f"{profile}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"プロファイルが見つかりません: {profile_path}")
        data = _deep_merge(data, _load_yaml(profile_path))
    return Config(data)
