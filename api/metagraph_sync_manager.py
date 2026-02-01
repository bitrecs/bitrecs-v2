import gc
import time
import logging
import traceback
import multiprocessing
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, Any, Tuple
from bittensor import Subtensor
import utils.logger as logger


class MetagraphSyncManager:
    """Dedicated manager to keep metagraph data fresh without leaking threads."""
    def __init__(self, network: str, netuid: int, sync_interval: int = 1800, max_cycles_before_restart: int = 6):
        self.network = network
        self.netuid = netuid
        self.sync_interval = sync_interval
        self.max_cycles_before_restart = max_cycles_before_restart
        self._snapshot: Dict[str, Dict[str, Any]] = {}
        self._synced_at: float | None = None
        self._stop_event = multiprocessing.Event()
        self._process: multiprocessing.Process | None = None
        self._queue: multiprocessing.Queue = multiprocessing.Queue()


    def start(self) -> None:
        if self._process and self._process.is_alive():
            return
        self._stop_event.clear()
        self._process = multiprocessing.Process(
            target=self._run,
            args=(self._queue, self._stop_event, self.network, self.netuid, self.sync_interval, self.max_cycles_before_restart),
            name="MetagraphSyncManager",
            daemon=True
        )
        self._process.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._process and self._process.is_alive():
            self._process.join(timeout=20)
            if self._process.is_alive():
                self._process.terminate()

    def get_snapshot(self) -> Tuple[Dict[str, Dict[str, Any]], float | None]:
        # Non-blocking get from queue
        try:
            while True:
                snapshot, synced_at = self._queue.get_nowait()
                self._snapshot = snapshot
                self._synced_at = synced_at
        except Exception:
            pass
        return dict(self._snapshot), self._synced_at

    @staticmethod
    def _run(queue, stop_event, network, netuid, sync_interval, max_cycles_before_restart) -> None:
        logger.info("MetagraphSyncManager process started")
        cycle_count = 0
        while not stop_event.is_set():
            subtensor = None
            tmp_metagraph = None
            try:                
                subtensor = Subtensor(network=network)
                tmp_metagraph = subtensor.metagraph(netuid=netuid)
                tmp_metagraph.sync()
                snapshot: Dict[str, Dict[str, Any]] = {}
                for neuron in tmp_metagraph.neurons:
                    axon = neuron.axon_info
                    snapshot[neuron.hotkey] = {
                        "uid": neuron.uid,
                        "ip": axon.ip if axon else None,
                        "port": axon.port if axon else None,
                        "stake": float(neuron.stake),
                        "last_update": neuron.last_update,
                        "coldkey": neuron.coldkey,
                    }
                queue.put((snapshot, time.time()))
                logger.info(f"Metagraph sync complete: {len(snapshot)} nodes")
            except Exception as e:
                logger.error(f"Metagraph sync failed: {e}")
                logger.error(traceback.format_exc())
            finally:
                # Cleanup (Subtensor/metagraph may not need explicit shutdown, but keep for safety)
                try:
                    del tmp_metagraph
                    del subtensor
                    gc.collect()
                except NameError:
                    pass
            cycle_count += 1
            if cycle_count >= max_cycles_before_restart:
                logger.info(f"\033[33mMetagraphSyncManager restarting after {cycle_count} cycles to clear memory leaks\033[0m")
                break
            stop_event.wait(sync_interval)
        logger.info("\033[31mMetagraphSyncManager process stopped \033[0m")

