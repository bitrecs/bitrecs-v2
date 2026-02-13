"""

Bitrecs CLI - Upload miner artifacts to the Bitrecs platform.

# https://github.com/ridgesai/ridges/blob/main/ridges.py 

"""
import os
import time
import httpx
import click
import subprocess
import hashlib
from bittensor_wallet.wallet import Wallet
from typing import Optional
from dotenv import load_dotenv

from models.agent import Agent
from models.miner_submission import MinerSubmission
from rules.agent_validator import validate_artifact_template
from utils.gist import get_gist, get_gist_created_at
load_dotenv()
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from bittensor import Subtensor
from version import __version__ as this_version


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

@cli.command()
@click.option("--github-account", help="GitHub account name")
@click.option("--gist-id", help="Gist ID containing your miner_artifact.yaml")
@click.option("--coldkey-name", help="Coldkey name")
@click.option("--hotkey-name", help="Hotkey name")
@click.option("--netuid", type=int, help="Netuid for the subnet")
@click.pass_context
def upload_burn(ctx, github_account: Optional[str], gist_id: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str], netuid: Optional[int]):
    """Upload a miner artifact to the Bitrecs API using alpha burn."""
    bitrecs = BitrecsCLI(ctx.obj.get('url'))

    if not any([github_account, gist_id]):
        console.print("Please provide either --github-account and --gist-id, or ensure the corresponding environment variables are set.", style="bold red")
        return
    if not any([coldkey_name, hotkey_name]):
        console.print("Please provide either --coldkey-name and --hotkey-name, or ensure the corresponding environment variables are set.", style="bold red")
        return
    
    coldkey = coldkey_name or get_or_prompt("OWNER_COLDKEY", "Enter your coldkey name", "default")
    hotkey = hotkey_name or get_or_prompt("BITRECS_HOTKEY_NAME", "Enter your hotkey name", "default")
    wallet = Wallet(name=coldkey, hotkey=hotkey)

    gist_created_at = get_gist_created_at(gist_id)
    gist_raw_data = get_gist(github_account, gist_id)   
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact)    
    if not validated:
        console.print(f"Artifact validation failed: {reason}", style="bold red")
        return    
    
    netuid = netuid or int(get_or_prompt("BITRECS_NETUID", "Enter the Netuid", "296"))

    #console.print(Panel(f"[bold cyan]Uploading Artifact (Burn Alpha)[/bold cyan]\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]File:[/yellow] {file}\n[yellow]API:[/yellow] {bitrecs.api_url}\n[yellow]Netuid:[/yellow] {netuid}", title="Upload Burn", border_style="cyan"))
    
    try:
        # with open(file, 'rb') as f:
        #     file_content = f.read()
        
        # content_hash = hashlib.sha256(file_content).hexdigest()
        
        public_key = wallet.hotkey.public_key.hex()

        name = Prompt.ask("Enter a name for your miner artifact")
        
        with httpx.Client() as client:
            #response = client.get(f"{bitrecs.api_url}/retrieval/agent-by-hotkey?miner_hotkey={wallet.hotkey.ss58_address}")
            
            # if response.status_code == 200 and response.json():
            #     latest_agent = response.json()
            #     name = latest_agent.get("name")
            #     version_num = latest_agent.get("version_num", -1) + 1
            # else:
            #     name = Prompt.ask("Enter a name for your miner artifact")
            #     version_num = 0

            # Check if artifact can be uploaded 
            version_num = 0 
            #check_file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
            # check_payload = {
            #     'public_key': public_key, 
            #     'file_info': check_file_info,
            #     'signature': wallet.hotkey.sign(check_file_info).hex(),
            #     'name': name,
            #     'payment_time': time.time()
            # }
            # check_response = client.post(f"{bitrecs.api_url}/upload/agent/check", files={'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}, data=check_payload, timeout=120)
            # if check_response.status_code != 200:
            #     console.print(f"Error checking agent: {check_response.text}", style="bold red")
            #     return

            # Send payment for evaluation
            payment_time_start = time.time()
            payment_response = client.get(f"{bitrecs.api_url}/upload/eval-pricing")

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

            chain_endpoint = os.getenv('SUBTENSOR_ADDRESS')
            network = os.getenv('SUBTENSOR_NETWORK', 'test')
            subtensor = Subtensor(network=chain_endpoint or network)
            
            # Burn Alpha
            # Call: burn_alpha(hotkey, amount, netuid)
            payment_payload = subtensor.substrate.compose_call(
                call_module="SubtensorModule",
                call_function="burn_alpha",
                call_params={
                    'hotkey': wallet.hotkey.ss58_address,
                    'amount': payment_method_details['amount_rao'],
                    'netuid': netuid                    
                }
            )

            payment_extrinsic = subtensor.substrate.create_signed_extrinsic(call=payment_payload, keypair=wallet.coldkey)
            
            with console.status("[bold green]Submitting burn transaction... (this may take a moment)[/bold green]"):
                receipt = subtensor.substrate.submit_extrinsic(payment_extrinsic, wait_for_finalization=True)

            if not receipt.is_success:
                console.print(f"\n[bold red]Burn Transaction Failed![/bold red]")
                console.print(f"[red]Block Hash:[/red] {receipt.block_hash}")
                try:
                    console.print(f"[red]Error:[/red] {receipt.error_message}")
                except:
                    pass
                return

          
            console.print(f"\n[yellow]Burn extrinsic submitted. If something goes wrong with the upload, you can use this information to get a refund")
            console.print(f"[cyan]Payment Block Hash:[/cyan] {receipt.block_hash}")
            console.print(f"[cyan]Payment Extrinsic Index:[/cyan] {receipt.extrinsic_idx}\n")

            #files = {'agent_file': ('agent.py', file_content, 'text/plain')}
            #files = {'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}
          
            preamble = f"{gist_created_at.isoformat()}:{github_account}:{gist_id}:{wallet.hotkey.ss58_address}"            
            signature = wallet.hotkey.sign(preamble).hex()
            submission = MinerSubmission(
                created_at=gist_created_at.isoformat(),
                github_account=github_account,
                gist_id=gist_id,
                hotkey=wallet.hotkey.ss58_address,
                signature=signature)

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                progress.add_task("Signing and uploading...", total=None)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Referer': f'{bitrecs.api_url}/'
                }
                submit_url =f"{bitrecs.api_url}/submit"
                response = client.post(submit_url, json=submission.to_dict(), timeout=120, headers=headers)
            
            if response.status_code == 201:
                console.print(Panel(f"[bold green]Upload Complete[/bold green]\n[cyan]Miner '{name}' uploaded successfully![/cyan]", title="Success", border_style="green"))
            else:
                error = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
                console.print(f"Upload failed (status {response.status_code}): {error}", style="bold red")
                    
    except Exception as e:
        console.print(f"Error: {e}", style="bold red")
        raise e


if __name__ == "__main__":
    run_cmd(". .venv/bin/activate")
    cli()