"""設定システム。

編集条件は全て設定ファイル（YAML）で管理する（仕様書 §7）。
default.yaml をベースに、案件プロファイルを深いマージで上書きする。
コードを書き換えずに ON/OFF・閾値変更・ルール追加ができる。
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import yaml

# リポジトリ直下（core/ の親）を基準にする。ハードコードした絶対パスは持たない。
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _ROOT / "config"
_DEFAULT = _CONFIG_DIR / "default.yaml"

_NUM = (int, float)

# 固定セクション: 許可キーと型。ここに無いキーは設定ミスとして早期に弾く。
_FIXED_SCHEMA: Dict[str, Dict[str, Union[Type, Tuple[Type, ...]]]] = {
    "project": {"name": str, "version": str},
    "timeline": {"merge_gap_sec": _NUM, "min_segment_sec": _NUM},
    "quality": {"report": bool, "max_removed_ratio": _NUM, "warn_min_segment_sec": _NUM},
    "export": {"format": str, "output_dir": str, "render": bool, "render_ext": str,
               "stem_suffix": str},
    "ai": {"enabled": bool, "provider": str, "model": str, "host": str, "timeout": _NUM},
}
# 開放セクション: 子キーはプラグイン名（任意）。子は dict で、enabled があれば bool。
_OPEN_SECTIONS = {"analysis", "rules"}
_ALLOWED_FORMATS = {"json", "edl", "html", "fcpxml"}


class ConfigError(ValueError):
    """設定ファイルの不正（未知キー・型違反・不正値）。"""


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


def _type_name(expected: Union[Type, Tuple[Type, ...]]) -> str:
    if isinstance(expected, tuple):
        return " または ".join(t.__name__ for t in expected)
    return expected.__name__


def _check_type(value: Any, expected: Union[Type, Tuple[Type, ...]]) -> bool:
    # bool は int のサブクラスなので、数値期待時に bool を弾く。
    if expected is bool:
        return isinstance(value, bool)
    if expected == _NUM:
        return isinstance(value, _NUM) and not isinstance(value, bool)
    return isinstance(value, expected)


def validate_config(data: Dict[str, Any]) -> List[str]:
    """設定を検証し、エラーメッセージの一覧を返す（空なら正常）。"""
    errors: List[str] = []
    known = set(_FIXED_SCHEMA) | _OPEN_SECTIONS

    for section, value in data.items():
        if section not in known:
            errors.append(f"未知のセクション: '{section}' (許可: {sorted(known)})")
            continue

        if section in _OPEN_SECTIONS:
            if not isinstance(value, dict):
                errors.append(f"'{section}' は辞書である必要があります")
                continue
            for name, opts in value.items():
                if not isinstance(opts, dict):
                    errors.append(f"'{section}.{name}' は辞書である必要があります")
                    continue
                if "enabled" in opts and not isinstance(opts["enabled"], bool):
                    errors.append(f"'{section}.{name}.enabled' は真偽値である必要があります")
            continue

        # 固定セクション
        schema = _FIXED_SCHEMA[section]
        if not isinstance(value, dict):
            errors.append(f"'{section}' は辞書である必要があります")
            continue
        for key, v in value.items():
            if key not in schema:
                errors.append(f"未知のキー: '{section}.{key}' (許可: {sorted(schema)})")
                continue
            if not _check_type(v, schema[key]):
                errors.append(
                    f"型違反: '{section}.{key}' は {_type_name(schema[key])} "
                    f"であるべきですが {type(v).__name__} です"
                )
            elif schema[key] == _NUM and isinstance(v, _NUM) and v < 0:
                errors.append(f"負値は不可: '{section}.{key}' = {v}")

    fmt = data.get("export", {}).get("format")
    if fmt is not None and fmt not in _ALLOWED_FORMATS:
        errors.append(f"不正な export.format: '{fmt}' (許可: {sorted(_ALLOWED_FORMATS)})")
    return errors


def load_config(profile: Optional[str] = None) -> Config:
    """default.yaml を読み、profile 指定時は config/profiles/<profile>.yaml で上書き。"""
    data = _load_yaml(_DEFAULT)
    if profile:
        profile_path = _CONFIG_DIR / "profiles" / f"{profile}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(f"プロファイルが見つかりません: {profile_path}")
        data = _deep_merge(data, _load_yaml(profile_path))

    errors = validate_config(data)
    if errors:
        raise ConfigError("設定エラー:\n  - " + "\n  - ".join(errors))
    return Config(data)
