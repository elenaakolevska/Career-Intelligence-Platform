import asyncio
import json
import urllib.request

try:
    import websockets
except ImportError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websockets', '-q'])
    import websockets


def post(path, body):
    req = urllib.request.Request(
        'http://localhost:8000/api/v1' + path,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


user = post('/users/', {'email': 'p806-ui@example.com', 'full_name': 'P806'})
sess = post(
    '/interview/start',
    {
        'user_id': user['id'],
        'role': 'Junior Java Developer',
        'difficulty': 'junior',
        'cv_id': 3,
    },
)
print('session', sess['id'])


async def run():
    uri = f"ws://localhost:8000/api/v1/interview/ws/{sess['id']}"
    async with websockets.connect(uri, open_timeout=30, ping_interval=20, ping_timeout=120) as ws:
        first = json.loads(await ws.recv())
        print('connected_msg', first['type'])
        await ws.send(json.dumps({'type': 'next_question'}))
        # May receive optional status then question
        q1 = json.loads(await ws.recv())
        if q1.get('type') == 'status':
            q1 = json.loads(await ws.recv())
        print('q1', q1['type'], (q1.get('question') or '')[:70])
        await ws.send(
            json.dumps(
                {
                    'type': 'answer',
                    'answer': (
                        'ArrayList is array-backed with O(1) access; LinkedList is node-based. '
                        'For example I use ArrayList for most Junior Java Developer API lists; '
                        'tradeoff is locality vs inserts.'
                    ),
                }
            )
        )
        f1 = json.loads(await ws.recv())
        if f1.get('type') == 'status':
            f1 = json.loads(await ws.recv())
        print('f1', f1['type'], f1.get('score'))
        await ws.send(json.dumps({'type': 'next_question'}))
        q2 = json.loads(await ws.recv())
        if q2.get('type') == 'status':
            q2 = json.loads(await ws.recv())
        print('q2', q2['type'], (q2.get('question') or '')[:70])
        await ws.send(
            json.dumps(
                {
                    'type': 'answer',
                    'answer': 'equals and hashCode must stay consistent for HashMap keys.',
                }
            )
        )
        f2 = json.loads(await ws.recv())
        if f2.get('type') == 'status':
            f2 = json.loads(await ws.recv())
        print(
            'f2',
            f2['type'],
            f2.get('score'),
            'turns',
            len((f2.get('session') or {}).get('history') or []),
        )
        await ws.send(json.dumps({'type': 'complete'}))
        done = json.loads(await ws.recv())
        print('done', done['type'], done.get('session', {}).get('status'))


asyncio.run(run())
