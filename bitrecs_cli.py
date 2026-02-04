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
load_dotenv()
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from bittensor import Subtensor
from version import __version__ as this_version


console = Console()
DEFAULT_API_BASE_URL = "https://v2.testnet.api.bitrecs.ai"
#DEFAULT_API_BASE_URL = "http://localhost:8000"



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

# @cli.command()
# @click.option("--file", help="Path to miner_artifact.yaml file")
# @click.option("--coldkey-name", help="Coldkey name")
# @click.option("--hotkey-name", help="Hotkey name")
# @click.pass_context
# def upload(ctx, file: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str]):
#     """Upload a miner artifact to the Bitrecs API."""
#     bitrecs = BitrecsCLI(ctx.obj.get('url'))
    
#     coldkey = coldkey_name or get_or_prompt("OWNER_COLDKEY", "Enter your coldkey name", "default")
#     hotkey = hotkey_name or get_or_prompt("BITRECS_HOTKEY_NAME", "Enter your hotkey name", "default")
#     wallet = Wallet(name=coldkey, hotkey=hotkey)

#     file = file or get_or_prompt("BITRECS_AGENT_FILE", "Enter the path to your miner_artifact.yaml file", "miner_artifact.yaml")
#     if not os.path.exists(file) or os.path.basename(file) != "miner_artifact.yaml":
#         console.print("File must be named 'miner_artifact.yaml' and exist", style="bold red")
#         return
    
#     console.print(Panel(f"[bold cyan]Uploading Artifact[/bold cyan]\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]File:[/yellow] {file}\n[yellow]API:[/yellow] {bitrecs.api_url}", title="Upload", border_style="cyan"))
    
#     try:
#         with open(file, 'rb') as f:
#             file_content = f.read()
        
#         content_hash = hashlib.sha256(file_content).hexdigest()
#         public_key = wallet.hotkey.public_key.hex()
        
#         with httpx.Client() as client:
#             #Basic headers for CF
#             headers = {
#                 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
#                 'Accept': 'application/json',
#                 'Referer': f'{bitrecs.api_url}/',
#             }            
            
#             response = client.get(f"{bitrecs.api_url}/retrieval/agent-by-hotkey?miner_hotkey={wallet.hotkey.ss58_address}", headers=headers)
            
#             if response.status_code == 200 and response.json():
#                 latest_agent = response.json()
#                 name = latest_agent.get("name")
#                 version_num = latest_agent.get("version_num", -1) + 1
#             else:
#                 name = Prompt.ask("Enter a name for your miner artifact")
#                 version_num = 0

#             # Check if artifact can be uploaded 
#             check_file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
#             check_payload = {
#                 'public_key': public_key, 
#                 'file_info': check_file_info,
#                 'signature': wallet.hotkey.sign(check_file_info).hex(),
#                 'name': name,
#                 'payment_time': time.time()
#             }
#             check_response = client.post(f"{bitrecs.api_url}/upload/agent/check", files={'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}, data=check_payload, timeout=120)
#             if check_response.status_code != 200:
#                 console.print(f"Error checking agent: {check_response.text}", style="bold red")
#                 return

#             # Send payment for evaluation
#             payment_time_start = time.time()
#             payment_response = client.get(f"{bitrecs.api_url}/upload/eval-pricing")

#             if payment_response.status_code != 200:
#                 console.print("Error fetching evaluation cost", style="bold red")
#                 return
            
#             payment_method_details = payment_response.json()
            
#             confirm_payment = Prompt.ask(
#                 f"\n[bold yellow]Proceed with payment of {payment_method_details['amount_rao']} RAO ({payment_method_details['amount_rao'] / 1e9} TAO) to {payment_method_details['send_address']}?[/bold yellow]", 
#                 choices=["y", "n"], 
#                 default="n"
#             )
#             if confirm_payment.lower() != "y":
#                 console.print("[bold red]Payment cancelled by user. Upload aborted.[/bold red]")
#                 return

#             chain_endpoint = os.getenv('SUBTENSOR_ADDRESS')
#             network = os.getenv('SUBTENSOR_NETWORK', 'test')
#             subtensor = Subtensor(network=network, chain_endpoint=chain_endpoint)

#             # Transfer
#             payment_payload = subtensor.substrate.compose_call(
#                 call_module="Balances",
#                 call_function="transfer_keep_alive",
#                 call_params={
#                     'dest': payment_method_details['send_address'], 
#                     'value': payment_method_details['amount_rao'],
#                 }
#             )

#             payment_extrinsic = subtensor.substrate.create_signed_extrinsic(call=payment_payload, keypair=wallet.coldkey)
#             receipt = subtensor.substrate.submit_extrinsic(payment_extrinsic, wait_for_finalization=True)

#             file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
#             signature = wallet.hotkey.sign(file_info).hex()
#             payload = {
#                 'public_key': public_key, 
#                 'file_info': file_info, 
#                 'signature': signature, 
#                 'name': name,
#                 'payment_block_hash': receipt.block_hash,
#                 'payment_extrinsic_index': receipt.extrinsic_idx,
#                 'payment_time': payment_time_start
#             }

#             console.print(f"\n[yellow]Payment extrinsic submitted. If something goes wrong with the upload, you can use this information to get a refund")
#             console.print(f"[cyan]Payment Block Hash:[/cyan] {receipt.block_hash}")
#             console.print(f"[cyan]Payment Extrinsic Index:[/cyan] {receipt.extrinsic_idx}\n")

#             #files = {'agent_file': ('agent.py', file_content, 'text/plain')}
#             files = {'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}

#             with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
#                 progress.add_task("Signing and uploading...", total=None)
#                 headers = {
#                     'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
#                     'Accept': 'application/json',
#                     'Referer': f'{bitrecs.api_url}/',
#                 }
#                 response = client.post(f"{bitrecs.api_url}/upload/agent", files=files, data=payload, headers=headers, timeout=120)
            
#             if response.status_code == 200:
#                 console.print(Panel(f"[bold green]Upload Complete[/bold green]\n[cyan]Miner '{name}' uploaded successfully![/cyan]", title="Success", border_style="green"))
#             else:
#                 error = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
#                 console.print(f"Upload failed: {error}", style="bold red")
                    
#     except Exception as e:
#         console.print(f"Error: {e}", style="bold red")
#         raise e

# @cli.command()
# @click.option("--file", help="Path to miner_artifact.yaml file")
# @click.option("--coldkey-name", help="Coldkey name")
# @click.option("--hotkey-name", help="Hotkey name")
# @click.option("--netuid", type=int, help="Netuid for the subnet")
# @click.pass_context
# def upload_stake(ctx, file: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str], netuid: Optional[int]):
#     """Upload a miner artifact to the Bitrecs API using stake transfer."""
#     bitrecs = BitrecsCLI(ctx.obj.get('url'))
    
#     coldkey = coldkey_name or get_or_prompt("OWNER_COLDKEY", "Enter your coldkey name", "default")
#     hotkey = hotkey_name or get_or_prompt("BITRECS_HOTKEY_NAME", "Enter your hotkey name", "default")
#     wallet = Wallet(name=coldkey, hotkey=hotkey)

#     file = file or get_or_prompt("BITRECS_AGENT_FILE", "Enter the path to your miner_artifact.yaml file", "miner_artifact.yaml")
#     if not os.path.exists(file) or os.path.basename(file) != "miner_artifact.yaml":
#         console.print("File must be named 'miner_artifact.yaml' and exist", style="bold red")
#         return
    
#     netuid = netuid or int(get_or_prompt("BITRECS_NETUID", "Enter the Netuid", "1"))

#     console.print(Panel(f"[bold cyan]Uploading Artifact (Stake Transfer)[/bold cyan]\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]File:[/yellow] {file}\n[yellow]API:[/yellow] {bitrecs.api_url}\n[yellow]Netuid:[/yellow] {netuid}", title="Upload Stake", border_style="cyan"))
    
#     try:
#         with open(file, 'rb') as f:
#             file_content = f.read()
        
#         content_hash = hashlib.sha256(file_content).hexdigest()
#         public_key = wallet.hotkey.public_key.hex()
        
#         with httpx.Client() as client:
#             response = client.get(f"{bitrecs.api_url}/retrieval/agent-by-hotkey?miner_hotkey={wallet.hotkey.ss58_address}")
            
#             if response.status_code == 200 and response.json():
#                 latest_agent = response.json()
#                 name = latest_agent.get("name")
#                 version_num = latest_agent.get("version_num", -1) + 1
#             else:
#                 name = Prompt.ask("Enter a name for your miner artifact")
#                 version_num = 0

#             # Check if artifact can be uploaded 
#             check_file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
#             check_payload = {
#                 'public_key': public_key, 
#                 'file_info': check_file_info,
#                 'signature': wallet.hotkey.sign(check_file_info).hex(),
#                 'name': name,
#                 'payment_time': time.time()
#             }
#             check_response = client.post(f"{bitrecs.api_url}/upload/agent/check", files={'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}, data=check_payload, timeout=120)
#             if check_response.status_code != 200:
#                 console.print(f"Error checking agent: {check_response.text}", style="bold red")
#                 return

#             # Send payment for evaluation
#             payment_time_start = time.time()
#             payment_response = client.get(f"{bitrecs.api_url}/upload/eval-pricing")

#             if payment_response.status_code != 200:
#                 console.print("Error fetching evaluation cost", style="bold red")
#                 return
            
#             payment_method_details = payment_response.json()
            
#             confirm_payment = Prompt.ask(
#                 f"\n[bold yellow]Proceed with STAKE TRANSFER of {payment_method_details['amount_rao'] / 1e9} ALPHA to {payment_method_details['send_address']} on Netuid {netuid}?[/bold yellow]", 
#                 choices=["y", "n"], 
#                 default="n"
#             )
#             if confirm_payment.lower() != "y":
#                 console.print("[bold red]Payment cancelled by user. Upload aborted.[/bold red]")
#                 return

#             chain_endpoint = os.getenv('SUBTENSOR_ADDRESS')
#             network = os.getenv('SUBTENSOR_NETWORK', 'test')
#             subtensor = Subtensor(network=chain_endpoint or network)
            
#             # Transfer Stake
#             payment_payload = subtensor.substrate.compose_call(
#                 call_module="SubtensorModule",
#                 call_function="transfer_stake",
#                 call_params={
#                     'destination_coldkey': payment_method_details['send_address'], 
#                     'hotkey': wallet.hotkey.ss58_address,
#                     'origin_netuid': netuid,
#                     'destination_netuid': netuid,
#                     'alpha_amount': payment_method_details['amount_rao'],
#                 }
#             )

#             payment_extrinsic = subtensor.substrate.create_signed_extrinsic(call=payment_payload, keypair=wallet.coldkey)
            
#             with console.status("[bold green]Submitting payment transaction... (this may take a moment)[/bold green]"):
#                 receipt = subtensor.substrate.submit_extrinsic(payment_extrinsic, wait_for_finalization=True)

#             if not receipt.is_success:
#                 console.print(f"\n[bold red]Payment Transaction Failed![/bold red]")
#                 console.print(f"[red]Block Hash:[/red] {receipt.block_hash}")
#                 try:
#                     console.print(f"[red]Error:[/red] {receipt.error_message}")
#                 except:
#                     pass
#                 return

#             file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
#             signature = wallet.hotkey.sign(file_info).hex()
#             payload = {
#                 'public_key': public_key, 
#                 'file_info': file_info, 
#                 'signature': signature, 
#                 'name': name,
#                 'payment_block_hash': receipt.block_hash,
#                 'payment_extrinsic_index': receipt.extrinsic_idx,
#                 'payment_time': payment_time_start
#             }

#             console.print(f"\n[yellow]Payment extrinsic submitted. If something goes wrong with the upload, you can use this information to get a refund")
#             console.print(f"[cyan]Payment Block Hash:[/cyan] {receipt.block_hash}")
#             console.print(f"[cyan]Payment Extrinsic Index:[/cyan] {receipt.extrinsic_idx}\n")

#             #files = {'agent_file': ('agent.py', file_content, 'text/plain')}
#             files = {'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}

#             with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
#                 progress.add_task("Signing and uploading...", total=None)
#                 response = client.post(f"{bitrecs.api_url}/upload/agent", files=files, data=payload, timeout=120)
            
#             if response.status_code == 200:
#                 console.print(Panel(f"[bold green]Upload Complete[/bold green]\n[cyan]Miner '{name}' uploaded successfully![/cyan]", title="Success", border_style="green"))
#             else:
#                 error = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
#                 console.print(f"Upload failed: {error}", style="bold red")
                    
#     except Exception as e:
#         console.print(f"Error: {e}", style="bold red")
#         raise e

@cli.command()
@click.option("--file", help="Path to miner_artifact.yaml file")
@click.option("--coldkey-name", help="Coldkey name")
@click.option("--hotkey-name", help="Hotkey name")
@click.option("--netuid", type=int, help="Netuid for the subnet")
@click.pass_context
def upload_burn(ctx, file: Optional[str], coldkey_name: Optional[str], hotkey_name: Optional[str], netuid: Optional[int]):
    """Upload a miner artifact to the Bitrecs API using alpha burn."""
    bitrecs = BitrecsCLI(ctx.obj.get('url'))
    
    coldkey = coldkey_name or get_or_prompt("OWNER_COLDKEY", "Enter your coldkey name", "default")
    hotkey = hotkey_name or get_or_prompt("BITRECS_HOTKEY_NAME", "Enter your hotkey name", "default")
    wallet = Wallet(name=coldkey, hotkey=hotkey)

    file = file or get_or_prompt("BITRECS_AGENT_FILE", "Enter the path to your miner_artifact.yaml file", "miner_artifact.yaml")
    if not os.path.exists(file) or os.path.basename(file) != "miner_artifact.yaml":
        console.print("File must be named 'miner_artifact.yaml' and exist", style="bold red")
        return
    
    netuid = netuid or int(get_or_prompt("BITRECS_NETUID", "Enter the Netuid", "296"))

    console.print(Panel(f"[bold cyan]Uploading Artifact (Burn Alpha)[/bold cyan]\n[yellow]Hotkey:[/yellow] {wallet.hotkey.ss58_address}\n[yellow]File:[/yellow] {file}\n[yellow]API:[/yellow] {bitrecs.api_url}\n[yellow]Netuid:[/yellow] {netuid}", title="Upload Burn", border_style="cyan"))
    
    try:
        with open(file, 'rb') as f:
            file_content = f.read()
        
        content_hash = hashlib.sha256(file_content).hexdigest()
        public_key = wallet.hotkey.public_key.hex()
        
        with httpx.Client() as client:
            response = client.get(f"{bitrecs.api_url}/retrieval/agent-by-hotkey?miner_hotkey={wallet.hotkey.ss58_address}")
            
            if response.status_code == 200 and response.json():
                latest_agent = response.json()
                name = latest_agent.get("name")
                version_num = latest_agent.get("version_num", -1) + 1
            else:
                name = Prompt.ask("Enter a name for your miner artifact")
                version_num = 0

            # Check if artifact can be uploaded 
            check_file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
            check_payload = {
                'public_key': public_key, 
                'file_info': check_file_info,
                'signature': wallet.hotkey.sign(check_file_info).hex(),
                'name': name,
                'payment_time': time.time()
            }
            check_response = client.post(f"{bitrecs.api_url}/upload/agent/check", files={'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}, data=check_payload, timeout=120)
            if check_response.status_code != 200:
                console.print(f"Error checking agent: {check_response.text}", style="bold red")
                return

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
                    'netuid': netuid,
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

            file_info = f"{wallet.hotkey.ss58_address}:{content_hash}:{version_num}"
            signature = wallet.hotkey.sign(file_info).hex()
            payload = {
                'public_key': public_key, 
                'file_info': file_info, 
                'signature': signature, 
                'name': name,
                'payment_block_hash': receipt.block_hash,
                'payment_extrinsic_index': receipt.extrinsic_idx,
                'payment_time': payment_time_start
            }

            console.print(f"\n[yellow]Burn extrinsic submitted. If something goes wrong with the upload, you can use this information to get a refund")
            console.print(f"[cyan]Payment Block Hash:[/cyan] {receipt.block_hash}")
            console.print(f"[cyan]Payment Extrinsic Index:[/cyan] {receipt.extrinsic_idx}\n")

            #files = {'agent_file': ('agent.py', file_content, 'text/plain')}
            files = {'agent_file': ('miner_artifact.yaml', file_content, 'text/plain')}

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                progress.add_task("Signing and uploading...", total=None)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Referer': f'{bitrecs.api_url}/'
                }
                response = client.post(f"{bitrecs.api_url}/upload/agent", files=files, data=payload, timeout=120, headers=headers)
            
            if response.status_code == 200:
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