
WHITELISTED_VALIDATORS = [
    {"hotkey": "5E7ooDPMFb8FMrnVD7z3B6ebkaNZRA5ksi87azE5okJsn122", "name": "RT21", "short_name": "RT21" },
    {"hotkey": "5C8DLjXNinbfJwgSxWGZTDKWYCpXSnjveB5Ng1ZJ2P7jEGUo", "name": "OTF", "short_name": "OTF" },
    {"hotkey": "5CXEbmzg7SD9dAsxep8MpjE28PbHxPotE63UnzLqu9VB99Tr", "name": "Bitrecs", "short_name": "Bitrecs" },
    {"hotkey": "5Dd76FfntpDjfYJK8Mwnq1yPTAw9QW7vHfxNQdiWxVgmkfk6", "name": "Yuma", "short_name": "Yuma" },
    {"hotkey": "5CZoa8Uw2GjkHfg3vybiiG5iGGAqqbDR6BdvhqJbj2Avs122", "name": "Rizzo", "short_name": "Rizzo" },  

    # Developer validators, used for testing    
    {"hotkey": "5DHtcX5EVi741Boi1ixAG8fpyV1kNku86D6oswjMkUGMAzTB", "name": "DimiTestValidator1", "short_name": "Dimi1" },  
    {"hotkey": "5HBjiUTERUJuAzXEeinA43Ffcwh9MMXPHz3FFEJ9eYgLwJaK", "name": "DimiTestValidator2", "short_name": "Dimi2" }

]

def is_validator_hotkey_whitelisted(validator_hotkey: str) -> bool:
    return validator_hotkey in [validator["hotkey"] for validator in WHITELISTED_VALIDATORS]

def validator_name_to_hotkey(validator_name: str) -> str:
    return next((validator["hotkey"] for validator in WHITELISTED_VALIDATORS if validator["name"] == validator_name), 'unknown')

def validator_hotkey_to_name(validator_hotkey: str) -> str:
    return next((validator["name"] for validator in WHITELISTED_VALIDATORS if validator["hotkey"] == validator_hotkey), 'unknown')