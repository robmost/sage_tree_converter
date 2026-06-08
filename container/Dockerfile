FROM python:3.13-slim

ARG DEBIAN_FRONTEND=noninteractive

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        hdf5-tools \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 LTS (required by Claude Code and Codex) ───────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── LLM CLIs ──────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code @openai/codex

# agy (Antigravity CLI) is distributed as a native binary, not an npm package.
# Build-time HOME is /root; move the binary to /usr/local/bin so it stays on
# PATH when HOME is overridden to /tmp at runtime.
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && mv ~/.local/bin/agy /usr/local/bin/agy

# ── Register common host UIDs so Node.js os.userInfo() does not crash ─────────
# Adds dummy passwd entries for UIDs 501/502 (macOS) and 1000/1001 (Linux).
RUN for uid in 501 502 1000 1001; do \
        grep -q ":${uid}:" /etc/passwd || \
        echo "user${uid}:x:${uid}:${uid}::/tmp:/bin/sh" >> /etc/passwd; \
    done

# ── Git: trust mounted volumes regardless of ownership ────────────────────────
RUN git config --system safe.directory '*'

# ── Python dependencies ────────────────────────────────────────────────────────
COPY pyproject.toml /tmp/pyproject.toml
RUN python3 -c "import tomllib; d=tomllib.loads(open('/tmp/pyproject.toml','rb').read()); deps=d['project']['dependencies']; import subprocess,sys; subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir']+deps)"

# ── Runtime environment ────────────────────────────────────────────────────────
ENV HOME=/tmp
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PS1='sage-sandbox:\w\$ '

WORKDIR /app

# Container starts idle; user attaches and runs the LLM CLI interactively.
CMD ["tail", "-f", "/dev/null"]
