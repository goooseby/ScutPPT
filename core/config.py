import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    # 下载目录（用户选择一次后保存）
    download_dir: Optional[str] = None

    # 下载力度（默认值偏保守，避免限流）
    max_workers: int = 8
    timeout: int = 60
    retries: int = 3
    sleep_ms: int = 200

    # 是否保留下载的原图（不保留则合并PDF后删除 images 目录）
    keep_images: bool = False


class ConfigStore:
    """
    配置文件固定放在程序目录：./config.json
    """
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.path = base_dir / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            # 配置损坏时给默认
            return AppConfig()

        cfg = AppConfig()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def save(self, cfg: AppConfig) -> None:
        self.path.write_text(
            json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
