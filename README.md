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
