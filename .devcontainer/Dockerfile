FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies including node and npm
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    make \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*


# Install pipx for the vscode user
USER vscode
RUN python3 -m pip install --user pipx && \
    python3 -m pipx ensurepath

# Install uv, pre-commit, and ruff using pipx
RUN /home/vscode/.local/bin/pipx install uv && \
    /home/vscode/.local/bin/pipx install pre-commit

# Add pipx binaries to PATH
ENV PATH="/home/vscode/.local/bin:${PATH}"
