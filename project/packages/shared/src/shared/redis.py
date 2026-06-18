# redis.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional, TypeVar

import redis
from redis import Redis

T = TypeVar("T")


@dataclass(frozen=True)
class RedisConfig:
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    decode_responses: bool = True
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class RedisClient:
    def __init__(self, config: RedisConfig | None = None) -> None:
        self.config = config or RedisConfig()
        self._client: Redis[str] = redis.Redis.from_url(
            self.config.url,
            decode_responses=self.config.decode_responses,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
        )

    @property
    def client(self) -> Redis[str]:
        return self._client

    def ping(self) -> bool:
        return bool(self._client.ping())

    def close(self) -> None:
        self._client.close()

    # ---------------------------
    # String / generic values
    # ---------------------------
    def set(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        return bool(self._client.set(key, value, ex=ex, px=px, nx=nx, xx=xx))

    def get(self, key: str, default: Any = None) -> Any:
        value = self._client.get(key)
        return default if value is None else value

    def delete(self, *keys: str) -> int:
        return int(self._client.delete(*keys))

    def exists(self, *keys: str) -> int:
        return int(self._client.exists(*keys))

    def expire(self, key: str, seconds: int) -> bool:
        return bool(self._client.expire(key, seconds))

    def ttl(self, key: str) -> int:
        return int(self._client.ttl(key))

    def incr(self, key: str, amount: int = 1) -> int:
        return int(self._client.incr(key, amount))

    def decr(self, key: str, amount: int = 1) -> int:
        return int(self._client.decr(key, amount))

    def update_value(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """
        Полная замена значения ключа.
        """
        return self.set(key, value, ex=ex)

    # ---------------------------
    # JSON helpers
    # ---------------------------
    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    def get_json(self, key: str, default: Any = None) -> Any:
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return default

    def patch_json(self, key: str, patch: dict[str, Any], ex: Optional[int] = None) -> bool:
        """
        Обновляет JSON-объект в ключе:
        - читает текущее значение
        - мержит словарь
        - записывает обратно
        """
        current = self.get_json(key, default={})
        if not isinstance(current, dict):
            current = {}
        current.update(patch)
        return self.set_json(key, current, ex=ex)

    # ---------------------------
    # Hash helpers
    # ---------------------------
    def hset(self, name: str, key: str, value: Any) -> int:
        return int(self._client.hset(name, key, value))

    def hmset(self, name: str, mapping: dict[str, Any]) -> bool:
        return bool(self._client.hset(name, mapping=mapping))

    def hget(self, name: str, key: str, default: Any = None) -> Any:
        value = self._client.hget(name, key)
        return default if value is None else value

    def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._client.hgetall(name))

    def hdel(self, name: str, *keys: str) -> int:
        return int(self._client.hdel(name, *keys))

    def hupdate(self, name: str, mapping: dict[str, Any]) -> bool:
        """
        Обновление hash в Redis.
        """
        return bool(self._client.hset(name, mapping=mapping))

    # ---------------------------
    # List helpers
    # ---------------------------
    def lpush(self, name: str, *values: Any) -> int:
        return int(self._client.lpush(name, *values))

    def rpush(self, name: str, *values: Any) -> int:
        return int(self._client.rpush(name, *values))

    def lpop(self, name: str, count: int = 1) -> Any:
        return self._client.lpop(name, count)

    def rpop(self, name: str, count: int = 1) -> Any:
        return self._client.rpop(name, count)

    def lrange(self, name: str, start: int, end: int) -> list[str]:
        return list(self._client.lrange(name, start, end))

    # ---------------------------
    # Set helpers
    # ---------------------------
    def sadd(self, name: str, *values: Any) -> int:
        return int(self._client.sadd(name, *values))

    def srem(self, name: str, *values: Any) -> int:
        return int(self._client.srem(name, *values))

    def smembers(self, name: str) -> set[str]:
        return set(self._client.smembers(name))

    def sismember(self, name: str, value: Any) -> bool:
        return bool(self._client.sismember(name, value))

    # ---------------------------
    # Search / maintenance
    # ---------------------------
    def keys(self, pattern: str = "*") -> list[str]:
        return list(self._client.keys(pattern))

    def scan_keys(self, pattern: str = "*", count: int = 100) -> list[str]:
        cursor = 0
        result: list[str] = []
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=count)
            result.extend(keys)
            if cursor == 0:
                break
        return result

    def flushdb(self) -> bool:
        return bool(self._client.flushdb())


redis_client = RedisClient()