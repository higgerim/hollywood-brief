"""Instagram API(Instagram 로그인 방식)로 카드뉴스를 캐러셀 게시물로 올려요.

필요한 환경변수:
  IG_USER_ID       인스타그램 비즈니스 계정 ID
  IG_ACCESS_TOKEN  장기 액세스 토큰 (instagram_business_basic, instagram_business_content_publish 권한)
"""
from __future__ import annotations

import os
import time

import requests


class InstagramError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    data = resp.json()
    if resp.status_code != 200 or "error" in data:
        raise InstagramError(f"Instagram API 오류 ({resp.status_code}): {data.get('error', data)}")
    return data


class Instagram:
    def __init__(self, api_version: str):
        self.base = f"https://graph.instagram.com/{api_version}"
        self.user_id = os.environ["IG_USER_ID"]
        self.token = os.environ["IG_ACCESS_TOKEN"]

    def _post(self, path: str, **params) -> dict:
        return _check(requests.post(f"{self.base}/{path}", data={**params, "access_token": self.token}, timeout=60))

    def _get(self, path: str, **params) -> dict:
        return _check(requests.get(f"{self.base}/{path}", params={**params, "access_token": self.token}, timeout=60))

    def _wait_ready(self, container_id: str, timeout: int = 300) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._get(container_id, fields="status_code")["status_code"]
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"미디어 처리 실패: {container_id} → {status}")
            time.sleep(5)
        raise InstagramError(f"미디어 처리 시간 초과: {container_id}")

    def publish_carousel(self, image_urls: list[str], caption: str) -> dict:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"캐러셀은 2~10장이어야 해요 (현재 {len(image_urls)}장)")
        children = []
        for url in image_urls:
            item = self._post(f"{self.user_id}/media", image_url=url, is_carousel_item="true")
            children.append(item["id"])
        for child in children:
            self._wait_ready(child)

        carousel = self._post(f"{self.user_id}/media", media_type="CAROUSEL",
                              children=",".join(children), caption=caption)
        self._wait_ready(carousel["id"])
        published = self._post(f"{self.user_id}/media_publish", creation_id=carousel["id"])
        info = self._get(published["id"], fields="id,permalink,timestamp")
        return info


def refresh_token(token: str) -> dict:
    """장기 토큰(60일)을 연장해요. 발급 후 24시간이 지나야 갱신할 수 있어요."""
    resp = requests.get("https://graph.instagram.com/refresh_access_token",
                        params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    return _check(resp)
