FROM python:3.13-slim

# Install system dependencies including Node.js to support Claude Code or npm-based AI CLIs
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    hdf5-tools \
    git \
    tesseract-ocr \
    poppler-utils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pre-pack the AI CLIs natively into the sandbox
RUN npm install -g @anthropic-ai/claude-code @google/gemini-cli

# Fix Git dubious ownership errors in mounted Docker volumes which lock up AI CLI background watchers
RUN git config --system --add safe.directory '*'

# Create dummy users for common host UID mappings (Mac/Linux) so Node.js os.userInfo() doesn't crash with ENOENT
RUN useradd -u 501 -d /tmp -s /bin/bash macuser1 && \
    useradd -u 502 -d /tmp -s /bin/bash macuser2 && \
    useradd -u 1000 -d /tmp -s /bin/bash linuxuser1 && \
    useradd -u 1001 -d /tmp -s /bin/bash linuxuser2

# Install python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove the default ID prompt and set a custom one
RUN echo 'export PS1="\\[\\e[36m\\]sage-sandbox\\[\\e[m\\]:\\w\\$ "' >> /etc/bash.bashrc

# The code will be mounted at runtime for easy modification by the LLM
CMD ["tail", "-f", "/dev/null"]
