# V2 Validator Setup

--Screener

sudo apt-get update
sudo apt-get upgrade

# Install Docker

sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

apt-cache policy docker-ce

sudo apt install docker-ce

sudo systemctl status docker

verify by typing: docker

# Install UV

curl -LsSf https://astral.sh/uv/install.sh | sh

reactivate shell:

source $HOME/.local/bin/env

uv sync


 