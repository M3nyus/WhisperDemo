import socketio
from aiohttp import web
import asyncio
import redis
import os
from dotenv import load_dotenv
from Logger import Logger


#SOCKETIO
sio = socketio.AsyncServer(cors_allowed_origins='*', ping_timeout=60, ping_interval=25)
app = web.Application()
sio.attach(app)

#LOAD .ENV
load_dotenv()

#LOGGER
LOGFILE = os.getenv("SERVER_LOG")
log = Logger(LOGFILE)

#CONFIGURATION
SERVER_HOST = os.getenv("SERVER_HOST")
SERVER_PORT = int(os.getenv("SERVER_PORT", "3000"))
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))

#REDIS
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

rooms = {}

#RUNINNG ROOMS
running_rooms = set()

#WORKER
workers = {}

room_worker_map = {}
worker_rooms = {}


#WEBCONNEVST
@sio.event
async def connect(sid, environ):
    print(f"[CONNECT] {sid}")
    log.Logging(f"[CONNECT] {sid}")
    await sio.emit("log", {
        "message": f"[CONNECT] {sid}"
    })


@sio.event
async def disconnect(sid):
    print(f"[DISCONNECT] {sid}")
    log.Logging(f"[DISCONNECT] {sid}")
    await sio.emit("log", {
        "message": f"[DISCONNECT] {sid}"
    })

    if sid in workers:
        del workers[sid]

    lost_rooms = worker_rooms.pop(sid, set())

    for room_id in lost_rooms:
        running_rooms.discard(room_id)
        room_worker_map.pop(room_id, None)

    await emit_available_workers()
    await emit_running_rooms()


#REGISTER
@sio.on("register_worker")
async def register_worker(sid, data):
    worker_id = data.get("clientId", sid)

    workers[sid] = {
        "sid": sid,
        "workerId": worker_id,
        "type": data.get("type", "bot_worker")
    }

    worker_rooms[sid] = set()

    await emit_available_workers()

    await sio.emit("log", {
        "message": f"Worker registered: {worker_id}"
    }, to=sid)


#COMMANDS
@sio.on("command")
async def handle_command(sid, data):
    print("[COMMAND FROM UI]", data)
    log.Logging(f"[COMMAND FROM UI] {sid}")
    await sio.emit("log", {
        "message": f"[COMMAND FROM UI] {data}"
    })

    action = data.get("action")
    room_id = data.get("roomId")
    worker_sid = data.get("workerSid")

    if action == "shutdown_worker":
        worker_sid = data.get("workerSid")

        if not worker_sid or worker_sid not in workers:
            await sio.emit("log", {
                "message": "Worker not found"
            })
            return

        await sio.emit("worker_command", {
            "action": "shutdown_worker"
        }, to=worker_sid)

        await sio.emit("log", {
            "message": f"Shutdown sent to worker: {workers[worker_sid]['workerId']}"
        })

        return

    if not room_id:
        await sio.emit("log", {
            "message": "Missing roomId"
        }, to=sid)
        return

    if action == "start_room":
        if room_id in room_worker_map:
            await sio.emit("log", {
                "roomId": room_id,
                "message": f"Room already running: {room_id}"
            }, to=sid)
            return

        worker_sid = get_least_busy_worker()

        if not worker_sid:
            await sio.emit("log", {
                "roomId": room_id,
                "message": "No available worker"
            }, to=sid)
            return

        room_worker_map[room_id] = worker_sid
        running_rooms.add(room_id)
        worker_rooms.setdefault(worker_sid, set()).add(room_id)

        await sio.emit("worker_command", data, to=worker_sid)

        await emit_available_workers()
        await emit_running_rooms()

        await sio.emit("log", {
            "roomId": room_id,
            "message": f"Room {room_id} assigned to {workers[worker_sid]['workerId']}"
        })
        return

    if action == "stop_room":
        worker_sid = room_worker_map.get(room_id)

        if not worker_sid:
            await sio.emit("log", {
                "roomId": room_id,
                "message": f"No worker assigned for room: {room_id}"
            }, to=sid)
            return

        await sio.emit("worker_command", data, to=worker_sid)

        running_rooms.discard(room_id)
        room_worker_map.pop(room_id, None)

        if worker_sid in worker_rooms:
            worker_rooms[worker_sid].discard(room_id)

        await emit_available_workers()
        await emit_running_rooms()

        await sio.emit("log", {
            "roomId": room_id,
            "message": f"Stop sent to assigned worker"
        }, to=sid)

        return

    if action == "transcribe_test":
        worker_sid = room_worker_map.get(room_id)

        if not worker_sid:
            worker_sid = get_least_busy_worker()

        if not worker_sid:
            await sio.emit("log", {
                "roomId": room_id,
                "message": "No available worker for transcription"
            }, to=sid)
            return

        #NOW NOT ACTIVE
        transcribe_job_id = f"transcribe:{room_id}:{data.get('chunkNumber')}"
        worker_rooms.setdefault(worker_sid, set()).add(transcribe_job_id)
        running_rooms.add(transcribe_job_id)

        await emit_available_workers()
        await emit_running_rooms()

        await sio.emit("worker_command", data, to=worker_sid)

        await sio.emit("log", {
            "roomId": room_id,
            "message": f"Transcribe sent to worker: {workers[worker_sid]['workerId']}"
        }, to=sid)

        return


# SUBTITLE FROM WORKER TO REFRESH
@sio.on("subtitle")
async def handle_subtitle(sid, data):
    print("[SUBTITLE FROM WORKER]", data)
    log.Logging(f"[SUBTITLE FROM WORKER] {data}")
    await sio.emit("log", {
        "message": f"[SUBTITLE FROM WORKER] {data}"
    })

    room_id = data.get("roomId")
    chunk_number = data.get("chunkNumber")

    transcribe_job_id = f"transcribe:{room_id}:{chunk_number}"

    if sid in worker_rooms:
        worker_rooms[sid].discard(transcribe_job_id)

    running_rooms.discard(transcribe_job_id)

    await emit_available_workers()
    await emit_running_rooms()
    await sio.emit("subtitle", data)


#WORKER LIST
@sio.on("get_worker_list")
async def get_worker_list_socket(sid):
    await emit_running_rooms(to=sid)
    await emit_available_workers(to=sid)

    await sio.emit("available_worker_list", {
        "workers": list(workers.values())
    }, to=sid)


#CHUNK NUMBER
@sio.on("get_chunk_count")
async def get_chunk_count(sid, data):
    room_id = data.get("roomId")

    if not room_id:
        await sio.emit("chunk_count", {
            "roomId": room_id,
            "count": 0
        }, to=sid)
        return

    pattern = f"{room_id}:*"
    keys = list(redis_client.scan_iter(match=pattern))

    chunk_numbers = []

    for key in keys:
        try:
            chunk_part = key.split(":")[1]

            if chunk_part.isdigit():
                chunk_numbers.append(int(chunk_part))
        except Exception:
            pass

    await sio.emit("chunk_count", {
        "roomId": room_id,
        "count": len(chunk_numbers),
        "chunks": sorted(chunk_numbers)
    }, to=sid)


#WEB
async def index(request):
    return web.FileResponse("templates/server.html")

async def client_page(request):
    return web.FileResponse("templates/client.html")


#MAIN ENDPOINTS
async def api_start_room(request):
    room_id = request.match_info["room_id"]

    await handle_command("api", {
        "action": "start_room",
        "roomId": room_id
    })

    return web.json_response({
        "status": "start_sent",
        "roomId": room_id
    })


async def api_stop_room(request):
    room_id = request.match_info["room_id"]

    await handle_command("api", {
        "action": "stop_room",
        "roomId": room_id
    })

    return web.json_response({
        "status": "stop_sent",
        "roomId": room_id
    })

app.router.add_get("/", index)
app.router.add_get("/client/{room_id}", client_page)
app.router.add_static("/static/", path="static", name="static")

app.router.add_get("/api/start/{room_id}", api_start_room)
app.router.add_post("/api/start/{room_id}", api_start_room)

app.router.add_get("/api/stop/{room_id}", api_stop_room)
app.router.add_post("/api/stop/{room_id}", api_stop_room)


async def start():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)

    print(f"Server running on http://{SERVER_HOST}:{SERVER_PORT}/")
    log.Logging(f"Server running on http://{SERVER_HOST}:{SERVER_PORT}/")

    await site.start()

    while True:
        await asyncio.sleep(3600)


#HELPERS
def get_room_list():
    return list(rooms.keys())

async def emit_available_workers(to=None):

    available = []

    for sid, worker in workers.items():

        room_count = len(worker_rooms.get(sid, set()))

        # CSAK SZABAD WORKER
        if room_count == 0:
            available.append({
                **worker,
                "runningRooms": []
            })

    payload = {
        "workers": available
    }

    if to:
        await sio.emit("available_worker_list", payload, to=to)
    else:
        await sio.emit("available_worker_list", payload)


async def emit_running_rooms(to=None):
    payload = {
        "workers": list(running_rooms)
    }

    if to:
        await sio.emit("worker_list", payload, to=to)
    else:
        await sio.emit("worker_list", payload)


def get_least_busy_worker():
    if not workers:
        return None

    return min(
        workers.keys(),
        key=lambda sid: len(worker_rooms.get(sid, set()))
    )

if __name__ == "__main__":
    asyncio.run(start())