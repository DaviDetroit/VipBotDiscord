import aiohttp
import asyncio
async def test_live():
    URL = "https://v3.football.api-sports.io/fixtures"
    HEADERS = {"x-apisports-key": "1cf0549436351d5fcfe87bf6da985484"}
    params = {"live": "all"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(URL, headers=HEADERS, params=params) as resp:
            data = await resp.json()
            print(data)

asyncio.run(test_live())



