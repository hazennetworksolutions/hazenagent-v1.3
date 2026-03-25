"""On-chain integration for HazenAgent — Base Mainnet proof of inference."""
import hashlib
import time
import asyncio
from typing import Optional

from src.utils.logger import logger

# ABI for HazenAgent contract (only the functions we call)
HAZEN_AGENT_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "prompt", "type": "string"}],
        "name": "requestInference",
        "outputs": [{"internalType": "bytes32", "name": "requestId", "type": "bytes32"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "requestId", "type": "bytes32"},
            {"internalType": "string", "name": "result", "type": "string"},
            {"internalType": "bytes32", "name": "proofHash", "type": "bytes32"}
        ],
        "name": "submitInference",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "quoteDispatch",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def _get_web3():
    """Get Web3 instance connected to Base Mainnet."""
    try:
        from web3 import Web3
        from config.settings import settings
        w3 = Web3(Web3.HTTPProvider(settings.base_rpc_url))
        return w3
    except ImportError:
        logger.warning("web3 not installed — on-chain features disabled")
        return None
    except Exception as e:
        logger.warning(f"Web3 init failed: {e}")
        return None


def _get_contract(w3):
    """Get HazenAgent contract instance."""
    from web3 import Web3
    from config.settings import settings

    address = settings.agent_contract_address
    if not address or address == "0xPLACEHOLDER":
        return None

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=HAZEN_AGENT_ABI
    )


async def _send_tx(w3, account, tx_params) -> Optional[object]:
    """Sign, send and wait for a transaction. Returns receipt or None."""
    signed = account.sign_transaction(tx_params)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash, timeout=60)


async def request_inference(prompt: str, nonce: int) -> Optional[tuple]:
    """Call requestInference(). Returns (request_id, nonce_used) or None."""
    w3 = _get_web3()
    if not w3:
        return None

    try:
        from config.settings import settings
        if not settings.agent_private_key:
            return None

        contract = _get_contract(w3)
        if not contract:
            return None

        account = w3.eth.account.from_key(settings.agent_private_key)
        fee = contract.functions.quoteDispatch().call()

        tx = contract.functions.requestInference(prompt).build_transaction({
            "from": account.address,
            "value": fee,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
        })

        receipt = await _send_tx(w3, account, tx)
        if receipt and receipt.status == 1:
            request_id = receipt.logs[0]["topics"][1].hex() if receipt.logs else ""
            logger.info(f"requestInference tx: {receipt.transactionHash.hex()}, requestId: {request_id}")
            return request_id

    except Exception as e:
        logger.warning(f"requestInference failed (non-critical): {e}")

    return None


async def submit_inference(request_id: str, result: str, nonce: int) -> bool:
    """Call submitInference(). Uses nonce+1 relative to requestInference."""
    w3 = _get_web3()
    if not w3:
        return False

    try:
        from config.settings import settings
        if not settings.agent_private_key:
            return False

        contract = _get_contract(w3)
        if not contract:
            return False

        account = w3.eth.account.from_key(settings.agent_private_key)

        proof_hash = hashlib.sha256(
            f"{request_id}:{result}:{int(time.time())}".encode()
        ).digest()

        request_id_bytes = bytes.fromhex(request_id.lstrip("0x").zfill(64))

        tx = contract.functions.submitInference(
            request_id_bytes,
            result[:200],
            proof_hash
        ).build_transaction({
            "from": account.address,
            "gas": 500000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce + 1,  # garantili sıradaki nonce
        })

        receipt = await _send_tx(w3, account, tx)
        if receipt and receipt.status == 1:
            logger.info(f"submitInference tx: {receipt.transactionHash.hex()}")
            return True

    except Exception as e:
        logger.warning(f"submitInference failed (non-critical): {e}")

    return False


async def record_inference(prompt: str, result: str) -> dict:
    """Full flow: request + submit. Nonce yönetimi burada yapılır."""
    from config.settings import settings

    contract_address = settings.agent_contract_address
    if not contract_address or contract_address == "0xPLACEHOLDER":
        return {"status": "skipped", "reason": "contract not deployed yet"}

    w3 = _get_web3()
    if not w3 or not settings.agent_private_key:
        return {"status": "skipped", "reason": "web3 or key not available"}

    account = w3.eth.account.from_key(settings.agent_private_key)
    base_nonce = w3.eth.get_transaction_count(account.address)

    request_id = await request_inference(prompt, nonce=base_nonce)
    if not request_id:
        return {"status": "skipped", "reason": "requestInference failed"}

    success = await submit_inference(request_id, result, nonce=base_nonce)
    return {
        "status": "recorded" if success else "partial",
        "request_id": request_id,
        "contract": contract_address,
        "network": "base-mainnet"
    }
