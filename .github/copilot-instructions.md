# Copilot instructions

<!-- beautyfast:start (managed by `bf init`; edits inside this block are replaced on re-run) -->
## Publishing on BeautyFast

This project is a **flask** app that is published on BeautyFast, P&G's internal app platform.
The user may be new to programming. Keep the code simple, explain what you change in plain language,
and keep the app runnable at every step.

### Settings: `build-config.yaml`
- BeautyFast builds the app from the GitHub repo using `build-config.yaml`. Keep it in the repo root.
- The server must listen on `0.0.0.0` port `5000`, and `startup_command` must start it:
  `gunicorn --bind 0.0.0.0:5000 app:app`. If you change the entry file, port or framework, update `build-config.yaml` to match.
- Runtime is `python-3.12`. Only use language features and packages that work there.
- Before changing `data_classification` or the `business_unit`/`function` tags, ask the user.

### Dependencies
- Every package the code imports must be listed in `requirements.txt`. A missing package is the most common reason a
  build or app start fails.
- Do not add a Dockerfile; BeautyFast builds the image itself.

### URLs and users
- The app is served at `https://beautyfast-prod.pg.com/<app-uuid>/`, not at the site root.
- In JavaScript and templates, use **relative** URLs (`fetch("api/items")`, `href="static/app.css"`), never ones starting with `/`. BeautyFast only rewrites leading-`/` links in HTML, not in `.js` files. The prefix is also sent in the `X-Forwarded-Prefix` header.
- BeautyFast already makes users sign in with their P&G account. Never add a login page or password handling.
- The signed-in user is in the request headers `X-User-Email`, `X-User-Name` and `X-User-Groups` (comma-separated). Use them instead of building a login.

### Files, secrets and network
- The app runs as a non-root user. Write files only under `/tmp` (or folders listed in `writable_paths`), and
  expect them to be deleted whenever the app restarts or is republished.
- For files that must be kept, run `bf storage create` here. It gives this app its own storage container: use
  `azure-storage-blob` with `os.environ["AZURE_STORAGE_CONNECTION_STRING"]` and the container named in
  `os.environ["BEAUTYFAST_STORAGE_CONTAINER"]` (both are also written to `.env` for running locally).
- Never put passwords, keys or tokens in code, `build-config.yaml` or git. Read them from environment variables
  (`os.environ` / `process.env`). Locally they go in `.env` in this folder (git-ignored); `bf deploy` gives them
  to the published app as secrets. Ask the user to type the values into `.env` themselves, never in chat.
- Outbound internet access from the app is restricted. Ask the user before relying on an external website or API.

### Trying it and publishing
- Run locally: install dependencies, then `python app.py`.
- The `bf` command line tool talks to BeautyFast. Add `--json` for machine-readable output. Run `bf info` first:
  it explains BeautyFast and shows where this project stands and what to do next. Other useful commands:
  `bf whoami` (signed in?), `bf deploy` (publish the code on GitHub), `bf status`, `bf logs` (runtime logs),
  `bf logs --build` (why a build failed), `bf open`. If `bf` says the user is not logged in, ask them to run
  `bf login`.
- Commit and push to GitHub before deploying; BeautyFast builds what is on GitHub, not local files.
<!-- beautyfast:end -->
