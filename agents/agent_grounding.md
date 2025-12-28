## Where you are and how you can touch things

- you are running inside a docker container.
- you have access to some extra tools such as ffmpeg probe and the like.
- you do not have access to inspect docker containers directly, you must write api endpoints to interact with the containers you build.
- you are connected to the same docker network as the containers you are working with.
- You are on a different docker stack as the containers you are building, but this should not matter?
- If you are working on the wallflower this can be found on your network with the DNS name thewallflower and the whisperlive instance is avalable at whisper-live.