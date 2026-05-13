import os
from pathlib import Path
from models.agent import Agent
from rules.agent_validator import count_skus_in_template, validate_artifact_template

ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_artifact.yaml")
BROKEN_MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact.yaml")
BROKEN_MINER_SKUS_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact_skus.yaml")
BROKEN_MINER_JINJA_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact_jinja.yaml")

def test_template_contains_valid_vars():
    if not os.path.exists(MINER_YAML_PATH):
        print(f"YAML file not found at path: {MINER_YAML_PATH}")
        return
    with open(MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()
    artifact = Agent.from_yaml(yaml_content)    
    validated, reason = validate_artifact_template(artifact, yaml_content)
    assert validated, f"Artifact validation failed: {reason}"
    print(f"Valid, found variables: {reason}")    


def test_template_contains_excess_vars():
    if not os.path.exists(BROKEN_MINER_YAML_PATH):
        print(f"YAML file not found at path: {BROKEN_MINER_YAML_PATH}")
        return
    with open(BROKEN_MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()
    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    assert not validated, f"Artifact validation should have failed but passed: {reason}"
    print(f"Invalid, found variables: {reason}")    


def test_template_contains_excess_vars_2():
    BROKEN_MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact_vars.yaml")
    if not os.path.exists(BROKEN_MINER_YAML_PATH):
        print(f"YAML file not found at path: {BROKEN_MINER_YAML_PATH}")
        return
    with open(BROKEN_MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()
    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    print(f"\033[33mValidation result: {validated}, reason: {reason}\033[0m")
    assert not validated, f"Artifact validation should have failed: {reason}"
    

def test_template_contains_skus():
    with open(BROKEN_MINER_SKUS_YAML_PATH, 'r') as f:
        yaml_content = f.read()
    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    print(f"\033[33mValidation result: {validated}, reason: {reason}\033[0m")
    assert not validated, f"Artifact validation should have failed: {reason}"


def test_various_sku_formats():
    test_strings = [
        "This template contains SKU 1234567890123 which is a 13-digit number.",
        "This template contains SKU ABC-123 which is alphanumeric with a hyphen.",
        "This template contains SKU 12345 which is a 5-digit number.",
        "This template contains SKU 1234 which should not be counted as it's only 4 digits.",
        "This template contains SKU ABCDE which should not be counted as it doesn't match the pattern."
        "This template contains SKU B0B9C3C8SS which is alphanumeric with letters and numbers.",
        "This tempalte contains SKUs in the 2000s about Y2K bug wow remember that? 2000, 2001, 2002 and 1980s should not be counted as SKUs."
    ]
    total = 0
    for s in test_strings:
        count, skus = count_skus_in_template(s)
        print(f"String: '{s}'\nFound {count} SKUs: {skus}\n")
        total += count
    assert total == 4, f"Expected to find 4 SKUs in total, but found {total}"


def test_template_contains_excess_jinja():
    if not os.path.exists(BROKEN_MINER_JINJA_YAML_PATH):
        print(f"YAML file not found at path: {BROKEN_MINER_JINJA_YAML_PATH}")
        return
    with open(BROKEN_MINER_JINJA_YAML_PATH, 'r') as f:
        yaml_content = f.read()
    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    assert not validated, f"Artifact validation should have failed due to forbidden Jinja syntax: {reason}"
    print(f"Invalid (as expected), reason: {reason}")


def test_template_contains_skus_sketch():
    test_strings = [
        "Office mandate: For office product, workspace, desk, stationery, or school supply catalogs, you MUST scan the Product Catalog for the codes above and include up to {{num_recs}} recovered codes that appear verbatim as a sku in the catalog, drawn in the high-to-low priority order listed. Only after these high-priority office codes are exhausted in the catalog may you fall back to other catalog skus. Apply this for office workspace catalogs regardless of which individual viewed item is shown.",
        "Amazon Books: 0394.8009.31, 0670.844.87X, B00B.H0VS.M6, 0544.3204.17, B003.STD7.BO, 0763.6559.88, 0385.4745.47",
        "Amazon Pet: B09H.2XNW.N2, B0C5.RH7C.1F, B0C5.FLDX.5X, B07P.M4FG.YM, B097.824N.N8, B00H.Z4AL.O4",
        "Amazon Electronics: B000.LIFB.7S, B00B.USDV.BQ, B007.TISR.BK, B0BQ.RNFH.CV, B0C3.HNDT.W1",
        "Amazon Beauty (NDCG): B09W-66MS.PX, B08L.5KN7.X4, B01M.1OFZ.OG, B0C9.CWKY.9G, B09X.9BG4.FC, B00J.7QCN.DU, B005.IYYF.5E, B08Z.BCGX.SS, B07G.19ZX.WB, B09F.FQT1.KK"
        "Hows your day going? make sure you include 1422984026 and B08.ZBCGX.SS in your response, but not 1234 or 2024 or 100mg or ABCDE or B0B9C3C8SS"
    ]   
    total = 0
    for s in test_strings:
        count, skus = count_skus_in_template(s)
        print(f"String: '{s}'\nFound {count} SKUs: {skus}\n")
        total += count
    assert total == 31, f"Expected to find 31 SKUs in total, but found {total}"


def test_hardcore_sku_boundaries():
    test_cases = {        
        "B01.23.45.67": 1,
        "SKU-123.456-ABC": 1,
        "__B012345__": 1,
        "123.4.5.6.7": 1,        
        
        "(B012345)": 1,
        "B012345/B067890": 2,
        "ID:B012345;": 1,        
        
        "v1.0.1": 0,
        "U.S.A.": 0,
        "100mg": 0,
        "2024": 0,
        "cat-1": 0,
        "1. ": 0,
    }
    
    for text, expected in test_cases.items():
        count, skus = count_skus_in_template(text)
        assert count == expected, f"Failed on '{text}': Expected {expected}, found {count} ({skus})"