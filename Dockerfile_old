FROM python:3.13-slim

# Update the base image
RUN apt-get update && apt-get upgrade -y

# Install dependencies
#RUN apt-get install -y curl sudo nano git htop netcat-openbsd wget unzip tmux apt-utils cmake build-essential

# Upgrade pip if needed for more robust env
RUN pip install --upgrade pip

# Install git
RUN apt-get install -y git
# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files (including uv.lock if it exists)
COPY pyproject.toml uv.lock* ./

# Install dependencies (remove --frozen if uv.lock is not present)
RUN uv sync --frozen

# Install bittensor (if not in pyproject.toml)
RUN uv add bittensor bittensor-wallet

# Copy the rest of the code
COPY . .

# Expose port
EXPOSE 8000

# Run the API
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]