  1. Which browser are you using? (Chrome, Firefox, Safari, Edge?)
  - answer : I have tried both edge and firefox, the same happens on both.
  2. What exactly happens?
    - Tab crashes with "Aw, Snap!" or similar?
    - answer : press the add stream button the browser slows to a crash within one second, you see the arrow wheel graphic not spinnitg.
    - Whole browser freezes?
    - answer : yes the whole browser freezes, no oh snap, just a hard lock, its like there is a memory leak.
    - Browser becomes unresponsive?
    - answer : correct, some times you can do things in the same browser but thewallflower tab is completley frozen, say for example if i type in to code-web in the same browser it may work, but my imputs are delayed by 10 seconds, or they may not work at all.
    - Something else?
  3. When exactly does it crash?
    - The moment you click "Create" in the modal? - Correct
    - After the modal closes? - the modal does close so you see the spinning arrow graphic (not spinning)
    - When the stream card appears? - it never appears
  4. What URL are you accessing the UI from? (e.g., http://192.168.x.x:8080 or something else) the URL im accessing it from is https://thewallflower.pownet.uk/ which is behind an nginx reverse proxy for https wrapping. 
  5. If you refresh the page after the crash, does it crash again immediately (since the stream is now in the DB)? I cant normally do this as the browser process crashes. No reposne to button clicks.