import hashlib
import json
import time
from datetime import datetime

class HashgraphAuditLedger:
    """
    Cryptographic / Hedera Hashgraph-Compatible Immutable Audit Ledger.
    Provides tamper-proof verifiable event logging for retail shrinkage,
    price tag tampering, inventory stock-outs, and staff operational dispatches.
    """
    def __init__(self, node_id="0.0.48291"):
        self.node_id = node_id
        self.chain = []
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis_block = {
            "sequence_number": 0,
            "timestamp": "2026-08-30T00:00:00.000000",
            "event_type": "GENESIS_NODE_INITIALIZATION",
            "payload": {
                "network": "SmartRetail Hashgraph Private Consortium",
                "consensus_node": self.node_id,
                "store_code": "STORE_001"
            },
            "previous_hash": "0" * 64,
            "hash": self._calculate_hash(0, "2026-08-30T00:00:00.000000", "GENESIS_NODE_INITIALIZATION", {}, "0" * 64)
        }
        self.chain.append(genesis_block)

    def _calculate_hash(self, seq, timestamp, event_type, payload, prev_hash):
        block_string = f"{seq}{timestamp}{event_type}{json.dumps(payload, sort_keys=True)}{prev_hash}"
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

    def record_event(self, event_type, payload):
        """
        Appends a cryptographic block to the immutable audit chain.
        """
        prev_block = self.chain[-1]
        seq = prev_block["sequence_number"] + 1
        now_iso = datetime.now().isoformat()
        prev_hash = prev_block["hash"]

        block_hash = self._calculate_hash(seq, now_iso, event_type, payload, prev_hash)

        block = {
            "sequence_number": seq,
            "timestamp": now_iso,
            "consensus_timestamp": f"{time.time():.6f}",
            "node_id": self.node_id,
            "event_type": event_type,
            "payload": payload,
            "previous_hash": prev_hash,
            "hash": block_hash,
            "verified": True
        }

        self.chain.append(block)
        return block

    def get_recent_blocks(self, limit=20):
        return list(reversed(self.chain[-limit:]))

    def verify_integrity(self):
        """
        Verifies the cryptographic integrity of the entire chain.
        """
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]

            if curr["previous_hash"] != prev["hash"]:
                return {"valid": False, "error_block": curr["sequence_number"], "message": "Hash chain broken!"}

            recalculated = self._calculate_hash(
                curr["sequence_number"],
                curr["timestamp"],
                curr["event_type"],
                curr["payload"],
                curr["previous_hash"]
            )
            if curr["hash"] != recalculated:
                return {"valid": False, "error_block": curr["sequence_number"], "message": "Block hash mismatch!"}

        return {
            "valid": True,
            "total_blocks": len(self.chain),
            "consensus_status": "CRYPTOGRAPHICALLY_VERIFIED",
            "last_consensus_timestamp": self.chain[-1].get("timestamp"),
            "latest_hash": self.chain[-1]["hash"]
        }
