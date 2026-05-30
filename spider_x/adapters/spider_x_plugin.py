"""Spider-X Adapter: SpiderXPlugin — 第三方API适配器（来自 spider_eco 独特功能）.

将 spider_eco 的动态第三方 API 注册/调用能力迁移到 Spider-X.
Spider-X 原有 adapters 只有结构适配，这个是实际可运行的 API 代理.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("spider_x.adapters.spider_x_plugin")


class SpiderXApiAdapter:
    """第三方 API 适配器：动态注册外部 API，通过名称调用.

    spider_eco spider_x/skill.py 独有功能迁移.
    支持：register_api_adapter / call_api / list_adapters / remove_adapter.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._api_mappings: Dict[str, Dict[str, Any]] = {}
        self._meta_url: str = ""

    def activate(self, meta_url: str = "", **kwargs) -> Dict[str, Any]:
        self._active = True
        self._meta_url = meta_url
        logger.info("SpiderXApiAdapter activated, meta_url=%s", meta_url)
        return {"status": "activated", "timestamp": datetime.now().isoformat()}

    def deactivate(self) -> Dict[str, Any]:
        self._active = False
        self._api_mappings.clear()
        return {"status": "deactivated"}

    def register_api_adapter(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        endpoint_map: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """注册一个第三方 API 适配器."""
        if not self._active:
            return {"error": "adapter not active"}
        self._api_mappings[name] = {
            "base_url": base_url.rstrip("/"),
            "api_key": api_key,
            "endpoint_map": endpoint_map or {},
            "headers": headers or {},
            "registered_at": datetime.now().isoformat(),
        }
        logger.info("API adapter registered: %s -> %s", name, base_url)
        return {"status": "registered", "adapter": name, "base_url": base_url}

    async def call_api(
        self,
        adapter_name: str,
        endpoint: str = "",
        method: str = "GET",
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """调用已注册的第三方 API."""
        if not self._active:
            return {"error": "adapter not active"}
        mapping = self._api_mappings.get(adapter_name)
        if not mapping:
            return {"error": f"adapter '{adapter_name}' not found"}

        url = f"{mapping['base_url']}/{endpoint.lstrip('/')}"
        headers = dict(mapping.get("headers", {}))
        if mapping.get("api_key"):
            headers["Authorization"] = f"Bearer {mapping['api_key']}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, params=params, json=data, headers=headers, timeout=timeout)
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text[:5000]}
            return {
                "status": "ok", "status_code": resp.status_code,
                "adapter": adapter_name, "endpoint": endpoint, "data": body,
            }
        except Exception as e:
            return {"status": "error", "adapter": adapter_name, "error": str(e)}

    def list_adapters(self) -> List[Dict[str, str]]:
        result = []
        for name, m in self._api_mappings.items():
            result.append({
                "name": name, "base_url": m["base_url"],
                "endpoints": len(m.get("endpoint_map", {})),
                "registered_at": m.get("registered_at", ""),
            })
        return result

    def remove_adapter(self, name: str) -> Dict[str, Any]:
        if name in self._api_mappings:
            del self._api_mappings[name]
            return {"status": "removed", "adapter": name}
        return {"error": f"adapter '{name}' not found"}

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self._active,
            "registered_adapters": len(self._api_mappings),
            "adapters": [n for n in self._api_mappings],
            "meta_url": self._meta_url,
        }
