import asyncio
import socketio
import uuid
import datetime
from Bot import Demo
from aiortc.contrib.media import MediaBlackhole
from trans import transcribe_from_redis_stream
import os
from dotenv import load_dotenv
from Logger import Logger

#SOCKETIO
sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0, reconnection_delay=1, reconnection_delay_max=10)

#LOAD .ENV
load_dotenv()

#LOGGER
LOGFILE = os.getenv("CLIENT_LOG")
log = Logger(LOGFILE)


CLIENT_ID = f"py-client-{uuid.uuid4().hex[:8]}"

workers_running = {}


#CONNECT TO SERVER
@sio.event
async def connect():
    print("[WORKER] Connected to server")
    log.Logging("[WORKER] Connected to server")

    await sio.emit("register_worker", {
        "type": "bot_worker",
        "clientId": CLIENT_ID
    })


#DISCONECT
@sio.event
async def disconnect():
    print("[WORKER] Disconnected")
    log.Logging("[WORKER] Disconnected")


#COMMANDS
@sio.on("worker_command")
async def handle_worker_command(data):
    print("[WORKER CMD]", data)
    log.Logging(f"[WORKER CMD], {data}")

    action = data.get("action")
    room_id = data.get("roomId")
    chunk_number = data.get("chunkNumber")

    #ROOM START
    if action == "start_room":

        if room_id in workers_running:
            print("Already running")
            log.Logging("Already running.")
            return

        demo = Demo(
            roomId=room_id,
            recorder=MediaBlackhole()
        )

        workers_running[room_id] = demo

        asyncio.create_task(demo.run())


        print(f"[WORKER] Room started: {room_id}")
        log.Logging("[WORKER] Room started: {room_id}")

    #ROOM STROP
    elif action == "stop_room":

        demo = workers_running.get(room_id)

        if demo:
            await demo.close()
            del workers_running[room_id]


            print(f"[WORKER] Room stopped: {room_id}")
            log.Logging("[WORKER] Room stopped: {room_id}")

    #TRANSCRIBE
    elif action == "transcribe_test":

        print("[CLIENT] running transcription...")
        log.Logging("[CLIENT] running transcription...")

        text = await asyncio.to_thread(
            transcribe_from_redis_stream,
            room_id,
            chunk_number
        )

        print("RESULT:\n", text)

        await sio.emit("subtitle", {
            "roomId": room_id,
            "chunkNumber": chunk_number,
            "text": text
        })

    #KILL WORKER
    elif action == "shutdown_worker":
        print("[WORKER] Shutdown requested")
        log.Logging("[WORKER] Shutdown requested")

        for room_id, demo in list(workers_running.items()):
            try:
                await demo.close()
            except Exception as e:
                print("Demo close error:", e)

        workers_running.clear()

        await sio.disconnect()

        asyncio.get_running_loop().stop()

async def worker_list():
    await sio.emit("worker_list", {
        "workers": list(workers_running.keys())
    })


#RUNNER
async def main():
    await sio.connect("http://localhost:3000")
    await sio.wait()

if __name__ == "__main__":
    asyncio.run(main())