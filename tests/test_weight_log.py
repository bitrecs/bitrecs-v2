# import pytest
# import sqlite3
# import os
# from datetime import datetime
# from unittest.mock import AsyncMock, MagicMock, patch
# from scoring.engine import log_weight_set

# @pytest.mark.asyncio
# async def test_log_weight_set():
#     # Mock inputs
#     netuid = 1
#     block = 100
#     val_key = MagicMock()
#     val_key.ss58_address = "validator_hotkey"
#     burn_weight = 0.5
#     miner_weight = 0.5
#     weight_receiving_uid = 1
    
#     # Mock subtensor and its methods
#     mock_subtensor = AsyncMock()
#     mock_validator_info = MagicMock()
#     mock_weight_receiving_info = MagicMock()
#     mock_weight_receiving_info.hotkey = "miner_hotkey"
#     mock_subtensor.get_validator_info.return_value = mock_validator_info
#     mock_subtensor.get_miner_info.return_value = mock_weight_receiving_info
    
#     # Mock get_subtensor to return the mock subtensor
#     with patch('scoring.engine.get_subtensor', return_value=mock_subtensor):
#         # Mock sqlite3 to avoid actual file I/O
#         with patch('sqlite3.connect') as mock_connect:
#             mock_conn = MagicMock()
#             mock_cursor = MagicMock()
#             mock_conn.cursor.return_value = mock_cursor
#             mock_connect.return_value = mock_conn
            
#             # Call the function (removed weights parameter to match actual function signature)
#             await log_weight_set(netuid, block, val_key, burn_weight, miner_weight, weight_receiving_uid)
            
#             # Assertions
#             mock_connect.assert_called_once_with('data/log/weight_log.db')
#             mock_cursor.execute.assert_any_call('''CREATE TABLE IF NOT EXISTS weight_log
#                  (timestamp TEXT, netuid INTEGER, block INTEGER, validator_hotkey TEXT, weight_receiving_uid INTEGER, weight_receiving_hotkey TEXT, miner_weight REAL, burn_weight REAL)''')
#             # Check insert call (timestamp will be dynamic, so check structure)
#             insert_call = mock_cursor.execute.call_args_list[1]
#             assert insert_call[0][0] == "INSERT INTO weight_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
#             args = insert_call[0][1]
#             assert args[1] == netuid
#             assert args[2] == block
#             assert args[3] == val_key.ss58_address
#             assert args[4] == weight_receiving_uid
#             assert args[5] == "miner_hotkey"
#             assert args[6] == miner_weight
#             assert args[7] == burn_weight
#             # Timestamp should be a string (ISO format)
#             assert isinstance(args[0], str)
#             mock_conn.commit.assert_called_once()
#             mock_conn.close.assert_called_once()