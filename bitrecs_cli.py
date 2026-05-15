"""
Bitrecs CLI - Upload miner artifacts to the Bitrecs platform.

"""
import os
import secrets
import time
import httpx
import click
import asyncio
import functools
import utils.logger as logger
from dotenv import load_dotenv
load_dotenv()
from bittensor_wallet.wallet import Wallet
from typing import Optional, Tuple
from models.agent import Agent
from models.miner_submission import MinerSubmission
from rules.agent_validator import validate_artifact_template
from rules.gist_validator import validate_artifact_gist
from utils.gist import get_gist, get_gist_created_at
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from version import __version__ as this_version
from utils.commitment import commit_to_chain_with_reveal
from utils.subtensor import close_subtensor
from utils.verify import create_transport_signature
from utils.commands import run_cmd
from utils.orkp import DEFAULT_KEY_CREDIT_LIMIT_USD, DEFAULT_KEY_EXPIRY_HOURS, create_temporary_openrouter_key
from llm.llm_provider import LLM

console = Console()
DEFAULT_API_BASE_URL = "https://v2.api.bitrecs.ai"
#DEFAULT_API_BASE_URL = "https://v2.testnet.api.bitrecs.ai"
#DEFAULT_API_BASE_URL = "http://localhost:8000"

console.print(f"Bitrecs CLI - Version {this_version} using Endpoint {DEFAULT_API_BASE_URL}", style="bold cyan")

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
async def upload(ctx, github_account: Optional[str], gist_id: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str], netuid: Optional[int]):
    """Upload a miner artifact to the Bitrecs API"""
    
    start_time = time.perf_counter()
    bitrecs = BitrecsCLI(ctx.obj.get('url'))
    netuid = netuid or int(get_or_prompt("NETUID", "Enter the Netuid", "122"))
    if not any([github_account, gist_id]):
        console.print("Please provide either --github-account and --gist-id, or ensure the corresponding environment variables are set.", style="bold red")
        return
    if not any([coldkey_name, hotkey_name]):
        console.print("Please provide either --coldkey-name and --hotkey-name, or ensure the corresponding environment variables are set.", style="bold red")
        return
    
    coldkey = coldkey_name or get_or_prompt("COLDKEY_NAME", "Enter your coldkey name", "default")
    hotkey = hotkey_name or get_or_prompt("HOTKEY_NAME", "Enter your hotkey name", "default")
    wallet = Wallet(name=coldkey, hotkey=hotkey)
    
    validated, reason = validate_artifact_gist(gist_id)
    if not validated:
        console.print(f"Artifact Gist validation failed: {reason}", style="bold red")
        return

    gist_raw_data = get_gist(github_account, gist_id)
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact, gist_raw_data)
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
    
    console.print(Panel(f"[bold cyan]Preparing to Upload Artifact with Commitment[/bold cyan]\n[yellow]GitHub Account:[/yellow] {github_account}\n[yellow]Gist ID:[/yellow] {gist_id}\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]Netuid:[/yellow] {netuid}", title="Upload", border_style="cyan"))
    try:
        logger.info(f"Starting upload with Commitment for Gist {gist_id} using wallet {wallet.hotkey.ss58_address} on Netuid {netuid}")        
        with httpx.Client() as client:
            console.print("Checking agent eligibility with the Bitrecs API...", style="dim")           
            check_response = client.post(f"{bitrecs.api_url}/check", json=submission.to_dict(), timeout=120)
            if check_response.status_code != 200:
                console.print(f"Error checking agent: {check_response.text}", style="bold red")
                return            

            provider = LLM.try_parse(artifact.provider)
            if provider == LLM.OPEN_ROUTER:
                console.print("This artifact uses OpenRouter as its provider, which requires a temporary API key to be generated and attached to your submission.\nThis key will be created with a limited lifespan and credit to ensure security. Do you want to proceed?", style="yellow")
                console.print("Note: you must have a valid OPENROUTER_MGMT_KEY environment variable set to use this feature.", style="yellow")
                proceed = Prompt.ask("Proceed with creating temporary OpenRouter key?", choices=["y", "n"], default="y")
                if not proceed or proceed.lower() != "y":
                    console.print("Aborting upload as per user request.", style="bold red")
                    return
                open_router_mgmt_key = os.getenv("OPENROUTER_MGMT_KEY")
                if not open_router_mgmt_key:
                    console.print("OPENROUTER_MGMT_KEY environment variable is not set. Please set it and try again.", style="bold red")
                    return
                temp_key = await create_temporary_openrouter_key(
                    mgmt_key=open_router_mgmt_key,
                    name=f"miner-{wallet.hotkey.ss58_address[:8]}-{gist_id}"
                )
                if temp_key is None or not temp_key.startswith("sk-or-v1-"):
                    console.print("Failed to create temporary OpenRouter key. Please check your OPENROUTER_MGMT_KEY and try again.", style="bold red")
                    console.print("For information on management keys see https://openrouter.ai/docs/guides/overview/auth/management-api-keys", style="bold red")
                    return
                else:
                    console.print("Temporary OpenRouter key created successfully and will be used for this submission.", style="bold green")
                    console.print(f"This key has a limit of {DEFAULT_KEY_CREDIT_LIMIT_USD} USD and expires in {DEFAULT_KEY_EXPIRY_HOURS} hours.", style="bold green")

            
            async def commit_to_chain_task() -> Tuple[bool, int]:
                commited, current_block = await commit_to_chain_with_reveal(submission.github_account, submission.gist_id, wallet)
                return commited, current_block
         
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:                
                commit_task_id = progress.add_task("Committing to chain...this can take up to 1 minute", total=None)
                commit_task = asyncio.create_task(commit_to_chain_task())
                await asyncio.gather(commit_task)
                progress.update(commit_task_id, completed=True)
            
            commited, current_block = commit_task.result()
            if not commited:
                console.print("Commitment to chain failed. Please check to ensure you are connected to the correct network and registered and try again.", style="bold red")                
                return
            
            console.print(f"\n[bold green]Commitment to chain successful on block {current_block}![/bold green]")          
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                # Wait for propogation
                prop_id = progress.add_task(f"Confirming blocks ... please stand by", total=None)
                await asyncio.sleep(24)
                progress.update(prop_id, completed=True)
            
                progress.add_task("Submitting artifact...", total=None)
                nonce = secrets.token_hex(16)
                ts = int(time.time())
                t_sig, t_nonce = create_transport_signature(wallet, submission, nonce, ts)
                headers = {                    
                    'Accept': 'application/json',
                    'Referer': f'{bitrecs.api_url}/',
                    'X-Signature': t_sig,
                    'X-Timestamp': str(ts),
                    'X-Nonce': nonce,
                    'X-T-Nonce': t_nonce
                }
                if provider == LLM.OPEN_ROUTER and temp_key:
                   headers["X-ORTK"] = temp_key
                       
                submit_url =f"{bitrecs.api_url}/submit"
                response = client.post(submit_url, json=submission.to_dict(), timeout=120, headers=headers)
            
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            console.print(f"Upload process took {elapsed:.2f} seconds.", style="dim")

            if response.status_code == 201:
                response_data = response.json()
                console.print(Panel(f"[bold green]Upload Complete[/bold green]\n[cyan]Artifact uploaded successfully![/cyan]", title="Success", border_style="green"))
                console.print(f"The {submission.github_account}/{submission.gist_id} artifact has been uploaded and is queued for evaluation.")
                artifact_id = response_data.get('artifact_id')
                console.print(f"Your artifact ID is: [yellow]{artifact_id}[/yellow]")
                artifact_url = f"https://dashboard.bitrecs.ai/agent/{artifact_id}"
                console.print(f"View your artifact here: [yellow]{artifact_url}[/yellow]")                
                
                request_id = response_data.get('request_id')
                message = response_data.get('message')
                similarity_check = response_data.get('similarity_check')
                similar_results = response_data.get('similar_results', [])
                
                console.print(f"\n[bold cyan]Response Details:[/bold cyan]")
                console.print(f"Request ID: [yellow]{request_id}[/yellow]")
                console.print(f"Message: [yellow]{message}[/yellow]")
                console.print(f"Similarity Check: [yellow]{similarity_check}[/yellow]")
                if similar_results:
                    console.print(f"Similar Agents:")
                    for result in similar_results:
                        agent_id = result.get('agent_id')
                        distance = result.get('distance')
                        console.print(f"  - Agent ID: [yellow]{agent_id}[/yellow], Distance: [yellow]{distance}[/yellow]")
                else:
                    console.print("No similar agents found.")
                console.print(f"Thank you for contributing to the Bitrecs ecosystem!", style="bold cyan")
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error') or error_data.get('detail') or 'Unknown error'
                    console.print(f"Upload failed (status {response.status_code}): {error_msg}", style="bold red")
                except ValueError:
                    console.print(f"Upload failed (status {response.status_code})", style="bold red")
                console.print("Your artifact was not uploaded - Please check the error message and try again.", style="bold red")
        
    except Exception as e:
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        logger.info(f"Upload failed after {elapsed:.2f} seconds with error: {str(e)}")  
        console.print(f"Error after {elapsed:.2f} seconds: {e}", style="bold red")
        raise e
    finally:
        await close_subtensor()



if __name__ == "__main__":    
    run_cmd(". .venv/bin/activate")
    cli()