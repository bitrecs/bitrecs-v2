"""

Bitrecs CLI - Upload miner artifacts to the Bitrecs platform.

# https://github.com/ridgesai/ridges/blob/main/ridges.py 

"""

import os
import secrets
import time
import httpx
import click
import asyncio
import subprocess
import functools
from dotenv import load_dotenv
load_dotenv()
import utils.logger as logger
from bittensor_wallet.wallet import Wallet
from typing import Optional
from models.agent import Agent
from models.miner_submission import MinerSubmission
from rules.agent_validator import validate_artifact_template
from rules.gist_validator import validate_artifact_gist
from utils.gist import get_gist, get_gist_created_at
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from bittensor import Subtensor
from version import __version__ as this_version
from utils.commitment import commit_to_chain_with_wallet
from async_substrate_interface import ExtrinsicReceipt
from utils.subtensor import close_subtensor

console = Console()
#DEFAULT_API_BASE_URL = "https://v2.testnet.api.bitrecs.ai"
DEFAULT_API_BASE_URL = "http://localhost:8000"


def run_cmd(cmd: str, capture: bool = True) -> tuple[int, str, str]:
    """Run command and return (code, stdout, stderr)"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            process = subprocess.Popen(cmd, shell=True)
            try:
                return_code = process.wait()
                return return_code, "", ""
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
    except KeyboardInterrupt:
        raise


def get_or_prompt(key: str, prompt: str, default: Optional[str] = None) -> str:
    """Get value from environment or prompt user."""
    value = os.getenv(key)
    if not value:
        value = Prompt.ask(f"{prompt}", default=default) if default else Prompt.ask(f"{prompt}")
    return value

class BitrecsCLI:
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or DEFAULT_API_BASE_URL
    

@click.group()
@click.version_option(version=this_version, prog_name="Bitrecs CLI")
@click.option("--url", help=f"Custom API URL (default: {DEFAULT_API_BASE_URL})")
@click.pass_context
def cli(ctx, url):
    """Bitrecs CLI - Manage your Bitrecs miners and validators"""
    ctx.ensure_object(dict)
    ctx.obj['url'] = url

def async_run(f):
    """Decorator to run async functions in Click."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@cli.command()
@click.option("--github-account", help="GitHub account name")
@click.option("--gist-id", help="Gist ID containing your miner_artifact.yaml")
@click.option("--coldkey-name", help="Coldkey name")
@click.option("--hotkey-name", help="Hotkey name")
@click.option("--netuid", type=int, help="Netuid for the subnet")
@click.pass_context
@async_run
async def upload_burn(ctx, github_account: Optional[str], gist_id: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str], netuid: Optional[int]):
    """Upload a miner artifact to the Bitrecs API using alpha burn."""
    
    start_time = time.perf_counter()
    bitrecs = BitrecsCLI(ctx.obj.get('url'))
    netuid = netuid or int(get_or_prompt("BITRECS_NETUID", "Enter the Netuid", "296"))    
    if not any([github_account, gist_id]):
        console.print("Please provide either --github-account and --gist-id, or ensure the corresponding environment variables are set.", style="bold red")
        return
    if not any([coldkey_name, hotkey_name]):
        console.print("Please provide either --coldkey-name and --hotkey-name, or ensure the corresponding environment variables are set.", style="bold red")
        return
    
    coldkey = coldkey_name or get_or_prompt("OWNER_COLDKEY", "Enter your coldkey name", "default")
    hotkey = hotkey_name or get_or_prompt("BITRECS_HOTKEY_NAME", "Enter your hotkey name", "default")
    wallet = Wallet(name=coldkey, hotkey=hotkey)
    
    validated, reason = validate_artifact_gist(gist_id)
    if not validated:
        console.print(f"Artifact Gist validation failed: {reason}", style="bold red")
        return

    gist_raw_data = get_gist(github_account, gist_id)
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact)
    if not validated:
        console.print(f"Artifact validation failed: {reason}", style="bold red")
        return

    gist_created_at = get_gist_created_at(gist_id)
    preamble = f"{gist_created_at.isoformat()}:{github_account}:{gist_id}:{wallet.hotkey.ss58_address}"
    signature = wallet.hotkey.sign(preamble).hex()
    submission = MinerSubmission(
        created_at=gist_created_at.isoformat(),
        github_account=github_account,
        gist_id=gist_id,
        hotkey=wallet.hotkey.ss58_address,
        signature=signature)
    
    console.print(Panel(f"[bold cyan]Preparing to Upload Artifact with Burn[/bold cyan]\n[yellow]GitHub Account:[/yellow] {github_account}\n[yellow]Gist ID:[/yellow] {gist_id}\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]Netuid:[/yellow] {netuid}", title="Upload Burn", border_style="cyan"))    
    
    try:
        logger.info(f"Starting upload with burn for Gist {gist_id} using wallet {wallet.hotkey.ss58_address} on Netuid {netuid}")
        
        with httpx.Client() as client:
            response = client.get(f"{bitrecs.api_url}/retrieval/agent-by-hotkey?miner_hotkey={wallet.hotkey.ss58_address}")
            if response.status_code == 200 and response.json().get('agent'):
                console.print(f"An agent is already registered with hotkey {wallet.hotkey.ss58_address}. Please use a different hotkey or remove the existing agent before uploading.", style="bold red")
                return
            else:
                console.print(f"No existing agent found with hotkey {wallet.hotkey.ss58_address}. Proceeding with upload.", style="bold green")
           
            check_response = client.post(f"{bitrecs.api_url}/check", json=submission.to_dict(), timeout=120)
            if check_response.status_code != 200:
                console.print(f"Error checking agent: {check_response.text}", style="bold red")
                return
        
            payment_response = client.get(f"{bitrecs.api_url}/eval-pricing")
            if payment_response.status_code != 200:
                console.print("Error fetching evaluation cost", style="bold red")
                return            
            payment_method_details = payment_response.json()            
            confirm_payment = Prompt.ask(
                f"\n[bold yellow]Proceed with BURNING of {payment_method_details['amount_rao'] / 1e9} ALPHA on Netuid {netuid}?[/bold yellow]", 
                choices=["y", "n"], 
                default="n"
            )
            if confirm_payment.lower() != "y":
                console.print("[bold red]Burn cancelled by user. Upload aborted.[/bold red]")
                return

            # Unlock wallets and pre-connect to subtensor before starting progress
            console.print("[dim]Decrypting wallets...[/dim]")
            coldkey_keypair = wallet.coldkey
            hotkey_keypair = wallet.hotkey
            hotkey_address = wallet.hotkey.ss58_address
            
            # Pre-connect to subtensor
            chain_endpoint = os.getenv('SUBTENSOR_ADDRESS')
            network = os.getenv('SUBTENSOR_NETWORK', 'test')
            subtensor = Subtensor(network=chain_endpoint or network)
            #subtensor = await get_subtensor()
            
            async def burn_alpha() -> ExtrinsicReceipt:
                payment_payload = subtensor.substrate.compose_call(
                    call_module="SubtensorModule",
                    call_function="burn_alpha",
                    call_params={
                        'hotkey': hotkey_address,  # Use cached address
                        'amount': payment_method_details['amount_rao'],
                        'netuid': netuid                    
                    }
                )
                payment_extrinsic = subtensor.substrate.create_signed_extrinsic(call=payment_payload, keypair=coldkey_keypair)
                receipt = await asyncio.to_thread(subtensor.substrate.submit_extrinsic, payment_extrinsic, wait_for_finalization=True)
                if not receipt.is_success:
                    raise Exception(f"Burn failed: {receipt.error_message}")
                console.print(f"\n[yellow]Burn extrinsic submitted...[/yellow]")
                console.print(f"[cyan]Payment Block Hash:[/cyan] {receipt.block_hash}")
                console.print(f"[cyan]Payment Extrinsic Index:[/cyan] {receipt.extrinsic_idx}\n")
                return receipt
            
            async def commit_to_chain_task() -> MinerSubmission:               
                commited, current_block = await commit_to_chain_with_wallet(submission.github_account, submission.gist_id, wallet)
                if not commited:
                    raise Exception("Commitment to chain failed")
                console.print(f"\n[bold green]Commitment to chain successful![/bold green]")
                return submission
            
            # Start progress 
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                burn_task_id = progress.add_task("Submitting burn transaction...", total=None)
                commit_task_id = progress.add_task("Committing to chain...", total=None)
                
                burn_task = asyncio.create_task(burn_alpha())
                commit_task = asyncio.create_task(commit_to_chain_task())
                await asyncio.gather(burn_task, commit_task)
                
                progress.update(burn_task_id, completed=True)
                progress.update(commit_task_id, completed=True)
            
            receipt = burn_task.result()
            submission = commit_task.result()

            payment_block_hash = receipt.block_hash
            payment_extrinsic_hash = receipt.extrinsic_hash
            #payment_block = receipt.block_number
            payment_extrinsic_index = receipt.extrinsic_idx
            
            console.print(f"payment_block_hash : {payment_block_hash}")
            console.print(f"payment_extrinsic_hash : {payment_extrinsic_hash}")
            #console.print(f"payment_block : {payment_block}")
            console.print(f"payment_extrinsic_index : {payment_extrinsic_index}")
            
            
            # Wait for reveal
            console.print(f"Waiting for reveal to be included on chain before uploading...")
            await asyncio.sleep(12)
            
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                progress.add_task("Submitting artifact...", total=None)                
                nonce = secrets.token_hex(16)
                submission_preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}:{payment_block_hash}:{payment_extrinsic_hash}:{payment_extrinsic_index}:{nonce}"
                transport_signature = wallet.hotkey.sign(submission_preamble).hex()                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Referer': f'{bitrecs.api_url}/',
                    'X-Signature': transport_signature,
                    'X-Timestamp': str(int(time.time())),
                    'X-Nonce': nonce,
                    'X-Payment-Block-Hash': payment_block_hash,
                    'X-Payment-Extrinsic-Hash': payment_extrinsic_hash,
                    'X-Payment-Extrinsic-Index': str(payment_extrinsic_index)
                }
                submit_url =f"{bitrecs.api_url}/submit"
                response = client.post(submit_url, json=submission.to_dict(), timeout=120, headers=headers)
            
            if response.status_code == 201:
                console.print(Panel(f"[bold green]Upload Complete[/bold green]\n[cyan]Artifact uploaded successfully![/cyan]", title="Success", border_style="green"))
                console.print(f"The {submission.github_account}/{submission.gist_id} artifact has been uploaded and is queued for evaluation. You can check the status of your submission on the Bitrecs platform.")
                artifact_id = response.json().get('artifact_id')
                console.print(f"Your artifact ID is: [yellow]{artifact_id}[/yellow]")
            else:
                error = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
                console.print(f"Upload failed (status {response.status_code}): {error}", style="bold red")
                try:
                    error_data = response.json()
                    print(f"Upload failed (status {response.status_code}): {error_data.get('error', 'Unknown error')}")
                    if 'details' in error_data:
                        print(f"Details: {error_data['details']}")
                    if 'traceback' in error_data and error_data['traceback']:
                        print(f"Traceback:\n{error_data['traceback']}")
                except ValueError:
                    # If not JSON, print raw text
                    print(f"Upload failed (status {response.status_code}): {response.text}")
            
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            console.print(f"Upload process took {elapsed:.2f} seconds.", style="dim")
        
        console.print(f"Thank you for contributing to the Bitrecs ecosystem!", style="bold cyan")
        await close_subtensor()
    except Exception as e:
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        logger.info(f"Upload failed after {elapsed:.2f} seconds with error: {str(e)}")  
        console.print(f"Error after {elapsed:.2f} seconds: {e}", style="bold red")
        raise e



if __name__ == "__main__":    
    run_cmd(". .venv/bin/activate")
    cli()