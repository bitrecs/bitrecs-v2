import asyncio
import docker
import subprocess
import threading
import utils.logger as logger

DOCKER_PREFIX = 'bitrecs-ai'
SWEBENCH_DOCKER_PREFIX = 'sweb'

docker_client = None
docker_lock = threading.Lock()

async def _initialize_docker():
    logger.info("Initializing Docker...")
    try:
        global docker_client
        with docker_lock:
            if docker_client is None:
                docker_client = await asyncio.to_thread(docker.from_env)
        logger.info("Initialized Docker")
    except Exception as e:
        logger.fatal(f"Failed to initialize Docker: {e}")

async def get_docker_client():
    if docker_client is None:
        await _initialize_docker()    
    return docker_client


async def build_docker_image(dockerfile_dir: str, tag: str) -> None:
    tag = f"{DOCKER_PREFIX}-{tag}"
    logger.info(f"Building Docker image: {tag}")
    await asyncio.to_thread(subprocess.run, ["docker", "build", "-t", tag, dockerfile_dir], text=True, check=True)
    logger.info(f"Successfully built Docker image: {tag}")


# async def get_num_docker_containers() -> int:
#     # This is equivalent to `docker ps -q | wc -l`
#     result = await asyncio.to_thread(subprocess.run, ["docker", "ps", "-q"], capture_output=True, text=True, timeout=1)
#     return len([line for line in result.stdout.strip().split('\n') if line.strip()])


async def get_num_docker_containers() -> int:
    """
    Get the number of running Docker containers using the Docker API.
    Returns None if Docker is not accessible (e.g., socket not mounted or no permissions).
    """
    try:
        client = docker.from_env()  # Connects via /var/run/docker.sock by default
        containers = client.containers.list()  # List running containers
        return len(containers)
    except docker.errors.DockerException as e:
        logger.warning(f"Docker API not accessible (likely not in DinD or socket not mounted): {e}")
        return 0
    except Exception as e:
        logger.warning(f"Unexpected error in get_num_docker_containers(): {e}")
        return 0


async def stop_and_delete_all_docker_containers() -> None:
    docker_client = await get_docker_client()
    
    logger.info(f"Stopping and deleting all containers...")
    
    containers = await asyncio.to_thread(docker_client.containers.list, all=True, filters={"name": f"^({DOCKER_PREFIX}|{SWEBENCH_DOCKER_PREFIX})"})
    
    for container in containers:
        logger.info(f"Stopping and deleting container {container.name}...")

        try:
            await asyncio.to_thread(container.stop, timeout=3)
        except Exception as e:
            logger.warning(f"Failed to stop container {container.name}: {e}")
            # continue
        
        try:
            await asyncio.to_thread(container.remove, force=True)
        except Exception as e:
            logger.warning(f"Failed to remove container {container.name}: {e}")
            continue

        logger.info(f"Stopped and deleted container {container.name}")

    await asyncio.to_thread(docker_client.containers.prune)
    
    logger.info(f"Stopped and deleted all containers")



async def create_internal_docker_network(name: str) -> None:
    docker_client = await get_docker_client()
    
    try:
        await asyncio.to_thread(docker_client.networks.get, name)
        logger.info(f"Found internal Docker network: {name}")
    except docker.errors.NotFound:
        await asyncio.to_thread(docker_client.networks.create, name, driver="bridge", internal=True)
        logger.info(f"Created internal Docker network: {name}")



async def connect_docker_container_to_internet(container: docker.models.containers.Container) -> None:
    docker_client = await get_docker_client()

    logger.info(f"Connecting Docker container {container.name} to internet...")

    bridge_network = await asyncio.to_thread(docker_client.networks.get, "bridge")
    await asyncio.to_thread(bridge_network.connect, container)
    
    logger.info(f"Connected Docker container {container.name} to internet")