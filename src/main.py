import asyncio
import pathlib

import aiohttp

fetch_queue = asyncio.Queue()
download_queue = asyncio.Queue()
album_url = 'https://www.ximalaya.com/revision/album/v1/getTracksList?albumId={album_id}&pageNum={page}'
download_url = 'https://www.ximalaya.com/revision/play/v1/audio?id={audio_id}&ptype=1'

session = aiohttp.ClientSession(headers={
    "accept": "*/*",
    "accept-language": "zh,zh-CN;q=0.9,zh-TW;q=0.8,en;q=0.7,en-US;q=0.6",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36"
})


async def run(album_id):
    print('starting fetcher & downloader...')
    await fetch_queue.put({
        'type': 'fetch_index',
        'album_id': album_id,
        'page': 1
    })
    await asyncio.gather(
        start_fetcher('1'),
        start_fetcher('2'),
    )
    await asyncio.gather(
        start_downloader('1'),
        start_downloader('2'),
    )
    await session.close()


async def start_fetcher(name):
    print(f'fetcher {name} started')
    while not fetch_queue.empty():
        job = await fetch_queue.get()
        print(f'fetcher {name} received job: {job}')
        if job['type'] == 'fetch_index':
            url = album_url.format(**job)
            print(f'fetcher {name} requesting {url}')
            response = await session.get(url)
            data = await response.json()
            # next page
            if len(data['data']['tracks']) == 0:
                continue
            await fetch_queue.put({
                'type': 'fetch_index',
                'album_id': job['album_id'],
                'page': job['page'] + 1,
            })
            # track download info
            for trackInfo in data['data']['tracks']:
                await fetch_queue.put({
                    'type': 'fetch_download_url',
                    'album_id': job['album_id'],
                    'audio_id': trackInfo['trackId'],
                    'trackInfo': trackInfo,
                })
        elif job['type'] == 'fetch_download_url':
            url = download_url.format(**job)
            print(f'fetcher {name} requesting {url}')
            response = await session.get(url)
            data = await response.json()
            if not data['data']['src']:
                continue
            url = data['data']['src']
            path = f'./{job["album_id"]}/{job["trackInfo"]["index"]:0>2}.{job["trackInfo"]["title"]}{pathlib.Path(url).suffix}'
            pathlib.Path(path).parent.mkdir(exist_ok=True)
            await download_queue.put({
                'path': path,
                'url': url
            })
        else:
            break
        fetch_queue.task_done()
    print(f'fetcher {name} died')


async def start_downloader(name):
    print(f'downloader {name} started')
    while not download_queue.empty():
        job = await download_queue.get()
        print(f'downloader {name} received job url: {job["url"]}')
        async with session.get(job['url']) as response:
            print(f'downloader {name} writing: {job["path"]}')
            fp = pathlib.Path(job['path']).open('wb')
            async for body, _ in response.content.iter_chunks():
                fp.write(body)
        download_queue.task_done()
    print(f'downloader {name} died')


loop = asyncio.get_event_loop()
loop.run_until_complete(run('33638348'))
