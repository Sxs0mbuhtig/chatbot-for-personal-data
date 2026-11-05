import asyncio
import httpx
import time

BATCH_TERMS = [
    "ស៊ីញ៉េ", "ប្រេកង់", "បាក់តេរី", "រ៉ាដា", 
    "ឡាស៊ែរ", "ហ្វ៊ីល", "ទូរទស្សន៍", "បណ្ដាញ"
]

async def fetch_term(client: httpx.AsyncClient, term: str):
    url = "http://localhost:8000/api/v1/search"
    start = time.perf_counter()
    try:
        response = await client.get(url, params={"q": term}, timeout=5.0)
        duration = time.perf_counter() - start
        return term, response.status_code, response.json(), duration
    except Exception as e:
        duration = time.perf_counter() - start
        return term, 500, {"error": str(e)}, duration

async def run_batch():
    print(f"Starting batch search resolution audit for {len(BATCH_TERMS)} terms...")
    async with httpx.AsyncClient() as client:
        tasks = [fetch_term(client, term) for term in BATCH_TERMS]
        results = await asyncio.gather(*tasks)
        
        for term, status, data, duration in results:
            print(f"[{status}] Query: {term} ({duration:.3f}s) -> Status: {data.get('status', 'error')}")

if __name__ == "__main__":
    asyncio.run(run_batch())
