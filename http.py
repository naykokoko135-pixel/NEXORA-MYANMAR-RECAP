import time
import requests

UA = {"User-Agent": "NexoraRecapBot/1.0 (https://github.com/naykokoko135-pixel/NEXORA-MYANMAR-RECAP)"}


def get(url, params=None, headers=None, tries=3, timeout=30, json_body=None):
    last = None
    for i in range(tries):
        try:
            h = {**UA, **(headers or {})}
            r = requests.post(url, json=json_body, params=params, headers=h, timeout=timeout) if json_body \
                else requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 ** (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"HTTP failed {url}: {last}")
