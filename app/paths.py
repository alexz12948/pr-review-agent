import os

# Compiled Vite assets (JS/CSS) live under frontend/dist; the dashboard route
# serves index.html and these assets are mounted under /static.
FRONTEND_DIST = os.path.join("frontend", "dist")
FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")
