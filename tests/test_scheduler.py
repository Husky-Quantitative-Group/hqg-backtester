import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import httpx

from fastapi.testclient import TestClient

from src.api.server import app
from src.scheduler.kv_store import kv_store


client = TestClient(app)

_STRATS_DIR = Path(__file__).parent / "test_strategies" / "strats"

_VALID_STRAT = (_STRATS_DIR / "strategy_01_momentum_spy_bnd_daily.py").read_text()

_SHORT_PAYLOAD = {
    "strategy_code": _VALID_STRAT,
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-06-01T00:00:00",
    "initial_capital": 10000.0,
}

_LONG_PAYLOAD = {
    "strategy_code": _VALID_STRAT,
    "start_date": "2019-01-01T00:00:00",
    "end_date": "2025-01-01T00:00:00",
    "initial_capital": 100000.0,
}

_STRATS = [f.read_text() for f in sorted(_STRATS_DIR.glob("*.py"))]

@asynccontextmanager
async def _running_scheduler():
    from src.scheduler.scheduler import scheduler
    task = asyncio.create_task(scheduler.run())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _poll_until_done(client: httpx.AsyncClient, job_id: str, *, timeout: float = 600) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        assert asyncio.get_running_loop().time() < deadline, \
            f"Job {job_id} did not finish within {timeout}s"
        resp = await client.get(f"/api/v1/backtest/{job_id}")
        if resp.status_code == 429:
            await asyncio.sleep(5)
            continue
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] == "COMPLETED":
            print("Job completed!")
            return data
        if data["status"] == "FAILED":
            print("Job failed")
            return data
        await asyncio.sleep(3)

@pytest.mark.asyncio
async def test_polling():
    from src.scheduler.scheduler import scheduler
    scheduler_task = asyncio.create_task(scheduler.run())

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            post_response = await client.post(
                "/api/v1/backtest",
                json=_LONG_PAYLOAD,
            )
            print(post_response.json())
            assert post_response.status_code == 202

            job_id = post_response.json()["job_id"]
            assert job_id is not None

            deadline = asyncio.get_event_loop().time() + 120
            final_data = None

            while True:
                assert asyncio.get_event_loop().time() < deadline, \
                    "Backtest did not finish within timeout"
                response = await client.get(f"/api/v1/backtest/{job_id}")
                assert response.status_code == 200

                data = response.json()
                status = data["status"]
                print(data)
                if status in {"COMPLETED", "FAILED"}:
                    final_data = data
                    break

                await asyncio.sleep(5)

            assert final_data is not None
            assert final_data["status"] == "COMPLETED"

            assert "job_id" in final_data
            assert final_data["job_id"] == job_id

            assert "metrics" in final_data["result"]
            assert "equity_stats" in final_data["result"]
            assert "candles" in final_data["result"]
            assert "orders" in final_data["result"]

            # Sanity check domain correctness
            assert final_data["result"]["equity_stats"]["equity"] > 0

    finally:
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)

        
@pytest.mark.asyncio
async def test_load():
    """Load test: 10 concurrent valid jobs"""
    N = 10
    payloads = [
        {**_SHORT_PAYLOAD, "strategy_code": _STRATS[i % len(_STRATS)]}
        for i in range(N)
    ]

    async with _running_scheduler():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            t0 = time.perf_counter()
            responses = await asyncio.gather(*[
                client.post("/api/v1/backtest", json=p) for p in payloads
            ])
            submission_elapsed = time.perf_counter() - t0

            job_ids = [r.json()["job_id"] for r in responses]
            assert all(r.status_code == 202 for r in responses)
            assert len(set(job_ids)) == N
            assert submission_elapsed < 10.0, \
                f"Submissions took {submission_elapsed:.2f}s — POST is blocking"

            results = await asyncio.gather(*[
                _poll_until_done(client, jid) for jid in job_ids
            ])

            assert all(d["status"] == "COMPLETED" for d in results)
            assert all(d["result"]["equity_stats"]["equity"] > 0 for d in results)
            assert kv_store._store == {}, "kv_store not empty after load test"


@pytest.mark.asyncio
async def test_stress():
    """Stress test: 20 concurrent jobs"""
    N = 20
    payloads = [
        {**_SHORT_PAYLOAD, "strategy_code": _STRATS[i % len(_STRATS)]}
        for i in range(N)
    ]

    async with _running_scheduler():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:

            responses = await asyncio.gather(*[
                client.post("/api/v1/backtest", json=p) for p in payloads
            ])

            job_ids = [r.json()["job_id"] for r in responses]
            assert all(r.status_code == 202 for r in responses)
            assert len(set(job_ids)) == N

            results = await asyncio.gather(*[
                _poll_until_done(client, jid, timeout=600) for jid in job_ids
            ])

            assert all(d["status"] == "COMPLETED" for d in results)
            assert all(d["result"]["equity_stats"]["equity"] > 0 for d in results)
            assert kv_store._store == {}, "kv_store leaked entries after stress test"


if __name__ == "__main__":
    import asyncio
    """
    Usage:
        python -m tests.test_scheduler
    """
    async def main():
        await test_load()

    asyncio.run(main())
