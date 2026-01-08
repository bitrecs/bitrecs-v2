

from enum import Enum


class BitrecsEval(Enum, str):
    PROMPT = "prompt"
    REASON = "reason"
    CATALOG = "catalog"
    RECALL = "recall"
    RANKING = "ranking"