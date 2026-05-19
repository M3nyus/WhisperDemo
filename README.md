# WhisperDemo

MAIN- FRONTEND

SERVER- Registers Clients

CLIENT- Component That is managed by server


```
cd server 
docker build -t menyus/zv-whisper-server .         
```

```
cd ..
cd main
docker build -t menyus/zv-whisper-main .         
```

```
cd ..
cd client
docker build -t menyus/zv-whisper-client .         
```

```
docker push menyus/zv-whisper-server
docker push menyus/zv-whisper-main
docker push menyus/zv-whisper-client
```