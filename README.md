Tic Tac Toe — Project

Run the app (system python):

C:/Python314/python.exe app.py

Open http://127.0.0.1:5000/ in a browser.

Run tests (requires pytest):

pip install -r requirements-dev.txt
pytest -q

Notes:
- The front-end uses localStorage to persist scores and theme.
- New features:
  - Select board size (3x3, 4x4, 5x5) before starting a game.
  - Deterministic AI option: toggle and provide a seed; the server will seed its RNG with the provided seed for reproducible machine moves.
  - GitHub Actions CI workflow at .github/workflows/ci.yml runs pytest on push/PR.
- The /play endpoint accepts JSON: { board, difficulty, player_symbol, mode, seed } and returns JSON with machine_move and winning_line when available.
# tic-tac-toe-game

Arena features:
- **Explain a move:** local and AI hints identify wins, blocks, and forks. On 3x3 boards, hints search for the best outcome against perfect play; larger boards use immediate tactics.
- **Match series:** choose Best of 3 or Best of 5, then press New series. First to 2 or 3 wins takes the series; draws award no points. Press Start Game after each round. X and O alternate starting. Series work in local and AI modes and last for the current page session. Loading a save or changing game mode, size, or human symbol ends the series.
- **Round replay:** use Previous and Next to review the current round without changing its board. Active local/AI games pause; close the replay and press Resume Game to continue. Wi-Fi games continue live.
- **Daily puzzle:** a shared UTC-date puzzle asks X to force a win in two moves against optimal defense. Try again freely; completion is stored in this browser, separately from match scores and trophies.
- **Wi-Fi rematches:** after a win or draw, both players press Vote for rematch. The board stays intact until both agree. Duplicate votes are harmless; old-round requests are rejected. Joined rooms keep their board size.

Browser regression tests require Chromium (`python -m playwright install chromium`). The existing end-to-end smoke test also expects the app running on port 5000.

Deploying to Railway:

1. Push the updated repository, including `requirements.txt`, `serve.py`, and `railway.json`, to the branch connected to Railway. Redeploy that service.
2. Railway uses `python serve.py` from `railway.json`. If you previously supplied a custom start command, check that the deployed configuration uses this command. The server binds to `0.0.0.0` on Railway's `PORT`; it does not use Flask's debug server.
3. In the service's **Settings → Networking → Public Networking**, choose **Generate Domain**. Share the resulting **HTTPS public domain**, not a dashboard link, `railway.internal` address, localhost, or a home-network IP address.
4. If the domain has a target port, it must match the app's `PORT`. A simple explicit setup is to set the service variable `PORT=8080` and the domain target port to `8080`, then redeploy.
5. Open `https://YOUR-PUBLIC-DOMAIN/health`; it should return `{"status":"ok"}`. Then open the root URL on another device using mobile data. Room invite links use `RAILWAY_PUBLIC_DOMAIN` when available and HTTPS in Railway's production server.
6. Keep **one replica in one region**. Rooms currently live in process memory, so they disappear after restarts or deployments; multiple replicas would not share rooms. SQLite trophies also need persistent storage before relying on them across deployments.

Troubleshooting: a failed build needs its build log checked; a crashed deployment needs its runtime log checked. A running service that returns Railway's “Application failed to respond” usually needs the bind address, `PORT`, and domain target port checked. A missing public domain must be generated in Networking. `/health` is a deployment readiness check, not continuous monitoring.

Local production check: install `requirements.txt`, run `python serve.py`, and open `http://127.0.0.1:5000/health`. Set `FLASK_DEBUG=1` only when you intentionally want debugging with `python app.py`.

References: [Railway public domains](https://docs.railway.com/networking/domains/working-with-domains), [Railway unreachable-service troubleshooting](https://docs.railway.com/networking/troubleshooting/application-failed-to-respond), [Waitress reverse-proxy setup](https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html).
