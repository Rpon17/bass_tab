# worker/main.py
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

# ✅ 너가 이미 만들어둔(혹은 만들 예정인) 워커 엔트리 함수들
# - submit_worker: "큐에서 job_id를 가져와 job을 처리"하는 루프/런너
# - communicate_worker: "ml_server와 통신(요청/응답)" 담당
#
# 아래 import 경로는 네 프로젝트 구조에 맞춰 바꿔줘.
from worker.submit_worker import submit_worker
from worker.communicate_worker import communicate_worker


# -------------------------
# Logging
# -------------------------
def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


# -------------------------
# Graceful shutdown helpers
# -------------------------
@dataclass
class Shutdown:
    event: asyncio.Event

    def request(self) -> None:
        self.event.set()

    async def wait(self) -> None:
        await self.event.wait()


def _install_signal_handlers(shutdown: Shutdown) -> None:
    """
    Windows/Unix 모두 고려:
    - asyncio loop에 signal handler 등록 가능한 경우 등록
    - 불가한 경우(Windows 일부 환경) KeyboardInterrupt로 종료되게 둠
    """
    loop = asyncio.get_running_loop()

    def _handler(sig: signal.Signals) -> None:
        logging.getLogger("worker").info("Shutdown requested by signal: %s", sig.name)
        shutdown.request()

    for s in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(s, _handler, s)


# -------------------------
# Main runner
# -------------------------
async def _run(args: argparse.Namespace) -> int:
    log = logging.getLogger("worker")
    shutdown = Shutdown(event=asyncio.Event())
    _install_signal_handlers(shutdown)

    # communicate_worker는 보통 "ML 서버 HTTP 클라이언트/세션"을 만든다고 가정
    # (예: httpx.AsyncClient 래핑) -> submit_worker에 주입
    #
    # communicate_worker의 반환 형태는 프로젝트에 따라 다를 수 있으니,
    # 여기서는 "ml_client 같은 객체"를 돌려준다고 가정하고 작성.
    ml_client = await communicate_worker(
        base_url=args.ml_base_url,
        timeout_sec=args.ml_timeout_sec,
    )

    # submit_worker는 큐/잡스토어 기반 무한루프를 돌면서
    # job_id pop -> job load -> ml_client 호출 -> job save 를 수행한다고 가정.
    #
    # shutdown_event를 넘겨서 graceful shutdown 가능하게.
    worker_task = asyncio.create_task(
        submit_worker(
            redis_url=args.redis_url,
            queue_name=args.queue_name,
            job_key_prefix=args.job_key_prefix,
            poll_interval_sec=args.poll_interval_sec,
            lock_ttl_sec=args.lock_ttl_sec,
            ml_client=ml_client,
            mode=args.mode,
            shutdown_event=shutdown.event,
        ),
        name="submit_worker",
    )

    log.info(
        "Worker started | queue=%s | redis=%s | ml=%s | mode=%s",
        args.queue_name,
        args.redis_url,
        args.ml_base_url,
        args.mode,
    )

    # shutdown event가 오면 worker_task를 정리
    await shutdown.wait()
    log.info("Shutting down...")

    worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await worker_task

    # communicate_worker가 클라이언트/세션을 열었다면 닫는 훅이 있을 수 있음
    # (예: ml_client.aclose()) 형태를 가정하고 안전하게 처리
    close = getattr(ml_client, "aclose", None)
    if callable(close):
        with suppress(Exception):
            await close()

    log.info("Shutdown complete.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="worker", description="Bass Project Worker (main_server queue -> ml_server)")
    p.add_argument("--redis-url", default="redis://localhost:6379/0", help="Redis connection URL")
    p.add_argument("--queue-name", default="youtube", help="Redis queue name")
    p.add_argument("--job-key-prefix", default="job:", help="Job key prefix in Redis (ex: job:)")
    p.add_argument("--ml-base-url", default="http://127.0.0.1:8001", help="ML server base url")
    p.add_argument("--ml-timeout-sec", type=float, default=120.0, help="ML request timeout seconds")

    p.add_argument(
        "--mode",
        default="full",
        choices=["separate", "analyze", "tab", "full"],
        help="ML processing mode",
    )

    p.add_argument("--poll-interval-sec", type=float, default=0.5, help="Queue polling interval seconds")
    p.add_argument("--lock-ttl-sec", type=int, default=60 * 10, help="Job lock TTL seconds")
    p.add_argument("--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING/ERROR)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.log_level)

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        # Windows에서 signal handler가 안 먹는 환경 대비
        logging.getLogger("worker").info("KeyboardInterrupt -> exit")
        return 0
    except Exception:
        logging.getLogger("worker").exception("Worker crashed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
