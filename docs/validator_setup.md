# V2 Validator Setup

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

# CLone Repo

git@github.com:bitrecs/bitrecs-v2.git

cd ~/bitrecs-v2
uv sync


 # PM2
 
 sudo apt install -y nodejs npm
 sudo npm install -g pm2
 
 pm2 init ecosystem
 
 edit the ecosystem.config.js
 
 module.exports = {
  apps: [{
    name:        "screener-2",
    script:      "sample_validator.py",
    cwd:         "/root/bitrecs-v2/validator",
    interpreter: "/root/.local/bin/uv",
    interpreter_args: "run",
    args:        "",
    exec_mode:   "fork",
    instances:   1,
    autorestart: true,
    watch:       false,
    max_memory_restart: "600M",
    env: {
      PYTHONUNBUFFERED: "1"
    }
  }]
};
 
pm2 start ecosystem
pm2 startup

pm2 logs 0

 