FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        hdf5-tools \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 LTS (required by Claude Code and Gemini CLI) ───────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── LLM CLIs ──────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code @google/gemini-cli

# ── Register common host UIDs so Node.js os.userInfo() does not crash ─────────
# Adds dummy passwd entries for UIDs 501/502 (macOS) and 1000/1001 (Linux).
RUN for uid in 501 502 1000 1001; do \
        grep -q ":${uid}:" /etc/passwd || \
        echo "user${uid}:x:${uid}:${uid}::/tmp:/bin/sh" >> /etc/passwd; \
    done

# ── Git: trust mounted volumes regardless of ownership ────────────────────────
RUN git config --system safe.directory '*'

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# ── Runtime environment ────────────────────────────────────────────────────────
ENV HOME=/tmp
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PS1='sage-sandbox:\w\$ '

WORKDIR /app

# Container starts idle; user attaches and runs the LLM CLI interactively.
CMD ["tail", "-f", "/dev/null"]
