import json
import os


def save_sync_watermark(path: str, timestamp: float) -> None:
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump({'last_sync': timestamp}, f)
    os.replace(tmp_path, path)
