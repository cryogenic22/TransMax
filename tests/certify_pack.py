
import sys
import os
import json
import re
import argparse
import asyncio
from typing import List, Dict, Any

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.services.quality_gate import QualityGateService

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class LanguagePackCertifier:
    def __init__(self, pack_code: str):
        self.pack_code = pack_code
        self.base_path = f"tests/language_packs/{pack_code}"
        self.config = self._load_json(f"{self.base_path}/config.json")
        self.golden_set = self._load_jsonl(f"{self.base_path}/golden.jsonl")
        self.core_cases = self._load_jsonl("tests/language_packs/core_cases.jsonl")
        self.gate_service = QualityGateService()

    def _load_json(self, path: str) -> Dict:
        if not os.path.exists(path):
            print(f"{Colors.FAIL}ERROR: Config not found at {path}{Colors.ENDC}")
            sys.exit(1)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_jsonl(self, path: str) -> List[Dict]:
        data = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content.startswith('['):
                    return json.loads(content)
                else:
                    # Fallback to actual JSONL
                    for line in content.splitlines():
                        if line.strip():
                            data.append(json.loads(line))
        return data

    def run(self, output_file: str = None):
        out_stream = open(output_file, 'w', encoding='utf-8') if output_file else sys.stdout
        
        def log(msg):
            print(msg, file=out_stream)
        
        log(f"=== Certifying Language Pack: {self.config['name']} ({self.pack_code}) ===")
        log(f"Config: {self.config}")
        log("-" * 50)
        
        log(f"\n--- Core Pharma Cases ---")
        for case in self.core_cases:
            self._run_check_internal(case, "core", log)
            
        log(f"\n--- {self.pack_code.upper()} Golden Cases ---")
        for case in self.golden_set:
            self._run_check_internal(case, "golden", log)
            
        if output_file:
            out_stream.close()

    def _run_check_internal(self, case: Dict, case_type: str, log_func):
        log_func(f"[{case_type.upper()}] Case {case['id']}: {case.get('desc', '')}")
        log_func(f"  Source: {case['source_text']}")
        
        target_lang = self.pack_code
        fake_target = case.get('source_text') # Dummy for now
        
        try:
            constraints = {
                "target_language": target_lang, 
                "glossary": []
            }
            violations = self.gate_service.check_segment(
                case['source_text'], 
                fake_target, 
                constraints
            )
            
            log_func(f"  Gate Response: {len(violations)} violations found.")
            for v in violations:
                log_func(f"    - {v['type']}: {v['message']}")
                
        except Exception as e:
            log_func(f"  CRASH: Backend failed to handle {self.pack_code}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True, help="Language pack code (ar, ja)")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()
    
    certifier = LanguagePackCertifier(args.pack)
    certifier.run(args.output)
