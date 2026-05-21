#!/usr/bin/env python3
"""
Script to analyze BUMP dataset merged test failures by running pre and breaking
Docker images and extracting structured failure information.
Adds a 'testFailure' section to each JSON file without modifying existing content.

Usage:
    python3 analyze_failures.py
    python3 analyze_failures.py [directory]
    python3 analyze_failures.py [directory] [workers]
    python3 analyze_failures.py [directory] [workers] --force
"""

import json
import subprocess
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --- Exclusion patterns (binary/infra noise, not BBCs) ---
EXCLUDE_PATTERNS = [
    r'NoSuchMethodError',
    r'NoClassDefFoundError',
    r'ClassNotFoundException',
    r'java\.net\.ConnectException',
    r'connect timed out',
    r'Connection refused',
]

# --- BBC signal patterns by category ---
FAILURE_CLASSIFICATION = {
    'TEST_ASSERTION': [
        r'AssertionError',
        r'expected:.*but was:',
        r'junit\.framework\.AssertionFailedError',
        r'org\.junit\.ComparisonFailure',
        r'AssertionFailedError',
        r'ComparisonFailure',
    ],
    'PROGRAM_ASSERTION': [
        r'AssertionError:\s+\w',
    ],
    'RUNTIME_EXCEPTION': [
        r'NullPointerException',
        r'IllegalStateException',
        r'IllegalArgumentException',
        r'ArrayIndexOutOfBoundsException',
        r'ClassCastException',
        r'NumberFormatException',
        r'IndexOutOfBoundsException',
    ],
    'CHECKED_EXCEPTION': [
        r'java\.io\.IOException',
        r'java\.sql\.SQLException',
        r'java\.net\.SocketException',
        r'java\.io\.FileNotFoundException',
    ],
    'ERROR': [
        r'ServiceConfigurationError',
        r'VerifyError',
        r'LinkageError',
        r'ExceptionInInitializerError',
    ],
    'RESOURCE_ERROR': [
        r'TestTimedOutException',
        r'SocketTimeoutException',
        r'OutOfMemoryError',
        r'StackOverflowError',
        r'ConditionTimeoutException',
    ],
}

print_lock = threading.Lock()


def tprint(*args, **kwargs):
    """Thread-safe print."""
    with print_lock:
        print(*args, **kwargs)


def run_docker(command: str, timeout: int = 600) -> str:
    """Run a docker command and return combined stdout+stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"DOCKER_ERROR: {str(e)}"


def remove_test_failure_section(content: str) -> str:
    """
    Remove any existing testFailure section from JSON content string.
    Uses bracket counting to handle nested objects safely.
    """
    if '"testFailure"' not in content:
        return content

    start = content.find('"testFailure"')
    if start == -1:
        return content

    # Find the comma before testFailure
    comma_pos = content.rfind(',', 0, start)
    if comma_pos == -1:
        return content

    # Find opening brace of testFailure value
    colon_pos = content.find(':', start)
    brace_start = content.find('{', colon_pos)
    if brace_start == -1:
        return content

    # Count braces to find matching closing brace
    depth = 0
    pos = brace_start
    brace_end = brace_start
    while pos < len(content):
        if content[pos] == '{':
            depth += 1
        elif content[pos] == '}':
            depth -= 1
            if depth == 0:
                brace_end = pos
                break
        pos += 1

    # Remove from comma to end of testFailure block
    end = brace_end + 1
    if end < len(content) and content[end] == '\n':
        end += 1

    cleaned = content[:comma_pos] + '\n' + content[end:]
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.rstrip()
    if not cleaned.endswith('}'):
        cleaned = cleaned + '\n}'
    else:
        cleaned = cleaned + '\n'

    return cleaned


def add_test_failure_section(json_path: Path, test_failure: dict,
                              force: bool = False) -> None:
    """
    Add testFailure section to JSON file without reformatting existing content.
    If force=True, removes any existing testFailure section first.
    """
    with open(json_path, 'r') as f:
        content = f.read()

    if '"testFailure"' in content:
        if not force:
            return
        content = remove_test_failure_section(content)

    # Build the new section as indented JSON
    new_section = json.dumps({"testFailure": test_failure}, indent=2)
    new_field = new_section[1:-1].strip()

    # Insert before the last closing brace
    last_brace = content.rstrip().rfind('}')
    modified = (
        content[:last_brace].rstrip()
        + ',\n  '
        + new_field
        + '\n'
        + content[last_brace:]
    )

    with open(json_path, 'w') as f:
        f.write(modified)


def extract_failing_module(output: str) -> Optional[str]:
    """Extract the Maven module that failed."""
    match = re.search(r'\[INFO\]\s+(\S+)\s+\.+\s+FAILURE', output)
    if match:
        return match.group(1)
    match = re.search(r'on project (\S+):', output)
    if match:
        return match.group(1)
    return None


def extract_failing_test_class(output: str) -> Optional[str]:
    """Extract the failing test class name."""
    match = re.search(r'Running ([\w\.]+)\n.*?(?:FAILURE|ERROR)', output, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'in ([\w\.]+)\s*<<<\s*(?:FAILURE|ERROR)', output)
    if match:
        return match.group(1)
    return None


def extract_failing_test_method(output: str) -> Optional[str]:
    """Extract the specific failing test method."""
    match = re.search(r'([\w\.]+)\s+Time elapsed:.*?<<<\s*(?:FAILURE|ERROR)', output)
    if match:
        return match.group(1)
    return None


def extract_error_details(output: str) -> Dict:
    """
    Extract the root error type, message and full exception class
    from the last Caused by block, or the first exception if no Caused by.
    """
    caused_by_blocks = re.findall(
        r'Caused by:\s+([\w\.\$]+(?:Exception|Error)[^\n]*)',
        output
    )

    if caused_by_blocks:
        root_exception_line = caused_by_blocks[-1]
    else:
        match = re.search(
            r'([\w\.\$]+(?:Exception|Error)):\s*([^\n]+)',
            output
        )
        root_exception_line = match.group(0) if match else ""

    exc_match = re.match(
        r'([\w\.\$]+(?:Exception|Error))(?::\s*(.+))?',
        root_exception_line
    )

    if exc_match:
        full_class = exc_match.group(1)
        message = (exc_match.group(2) or "").strip()
        short_name = full_class.split('.')[-1]
        return {
            'errorType': short_name,
            'errorClass': full_class,
            'errorMessage': message[:200] if message else None,
        }

    return {
        'errorType': None,
        'errorClass': None,
        'errorMessage': None,
    }


def classify_failure(output: str) -> Tuple[str, str, str]:
    """
    Returns (failureType, errorCategory, matched_pattern).
    """
    for pattern in FAILURE_CLASSIFICATION['TEST_ASSERTION']:
        if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
            return 'TEST_FAILURE', 'TEST_ASSERTION', pattern

    for pattern in FAILURE_CLASSIFICATION['PROGRAM_ASSERTION']:
        if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
            return 'TEST_FAILURE', 'PROGRAM_ASSERTION', pattern

    for category in ['RUNTIME_EXCEPTION', 'CHECKED_EXCEPTION', 'ERROR', 'RESOURCE_ERROR']:
        for pattern in FAILURE_CLASSIFICATION[category]:
            if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
                return 'TEST_ERROR', category, pattern

    return 'UNKNOWN', 'UNKNOWN', ''


def is_excluded(output: str) -> Tuple[bool, Optional[str]]:
    """Check if the failure is infrastructure/binary noise, not a BBC."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return True, pattern
    return False, None


def is_pre_existing(pre_output: str, breaking_output: str) -> bool:
    """
    Check if the same failure exists in the pre-commit image.
    """
    pre_details = extract_error_details(pre_output)
    breaking_details = extract_error_details(breaking_output)

    if (pre_details['errorType'] and breaking_details['errorType'] and
            pre_details['errorType'] == breaking_details['errorType']):
        print(f"  → Same error type in PRE and BREAKING: {pre_details['errorType']}")
        return True

    pre_fails = bool(re.search(
        r'Tests run:.*Failures: [1-9]|Tests run:.*Errors: [1-9]', pre_output
    ))
    breaking_fails = bool(re.search(
        r'Tests run:.*Failures: [1-9]|Tests run:.*Errors: [1-9]', breaking_output
    ))

    return pre_fails and breaking_fails


def infer_root_cause(error_type: str, error_message: str,
                     dependency: Dict, failure_category: str) -> str:
    """Generate a human-readable root cause description."""
    dep_name = (
        f"{dependency.get('dependencyGroupID', '')}/"
        f"{dependency.get('dependencyArtifactID', '')}"
    )
    prev_ver = dependency.get('previousVersion', '?')
    new_ver = dependency.get('newVersion', '?')
    version_str = f"{dep_name} {prev_ver} → {new_ver}"

    if error_type == 'NoSuchMethodError':
        return f"API version incompatibility: method removed or changed between {version_str}"
    elif error_type in ('NoClassDefFoundError', 'ClassNotFoundException'):
        return f"Class missing after update: binary incompatibility in {version_str}"
    elif failure_category == 'TEST_ASSERTION':
        return f"Library behaviour changed between {version_str}, causing assertion mismatch"
    elif failure_category == 'RUNTIME_EXCEPTION':
        return f"Precondition violation or changed internal state after updating {version_str}"
    elif failure_category == 'CHECKED_EXCEPTION':
        return f"New checked exception thrown after updating {version_str}"
    elif failure_category == 'ERROR':
        return f"JVM-level error after updating {version_str}"
    elif failure_category == 'RESOURCE_ERROR':
        return f"Resource or timeout issue after updating {version_str}"
    else:
        return f"Unknown failure after updating {version_str}"


def analyze_file(json_path: Path, idx: int, total: int,
                 force: bool = False) -> str:
    """
    Process a single benchmark JSON file.
    Returns status: BBC_CANDIDATE | PRE_EXISTING | EXCLUDED | SKIPPED | ERROR | UNKNOWN
    """
    tprint(f"[{idx}/{total}] {json_path.name}")

    try:
        with open(json_path, 'r') as f:
            content = f.read()
            data = json.loads(content)
    except Exception as e:
        tprint(f"  ✗ Failed to read file: {e}")
        return 'ERROR'

    if '"testFailure"' in content and not force:
        tprint(f"  → Already analyzed, skipping (use --force to overwrite)")
        return 'SKIPPED'

    pre_cmd = data.get('preCommitReproductionCommand', '')
    breaking_cmd = data.get('breakingUpdateReproductionCommand', '')
    dependency = data.get('updatedDependency', {})

    if not pre_cmd or not breaking_cmd:
        tprint(f"  ✗ Missing Docker commands")
        return 'ERROR'

    tprint(f"  Running PRE image...")
    pre_output = run_docker(pre_cmd)

    tprint(f"  Running BREAKING image...")
    breaking_output = run_docker(breaking_cmd)

    # Extract all details upfront regardless of status
    error_details = extract_error_details(breaking_output)
    failing_module = extract_failing_module(breaking_output)
    failing_test_class = extract_failing_test_class(breaking_output)
    failing_test_method = extract_failing_test_method(breaking_output)
    failure_type, error_category, matched = classify_failure(breaking_output)
    root_cause = infer_root_cause(
        error_details['errorType'] or '',
        error_details['errorMessage'] or '',
        dependency,
        error_category
    )

    base_info = {
        'failingModule': failing_module,
        'failingTestClass': failing_test_class,
        'failingTestMethod': failing_test_method,
        'failureType': failure_type,
        'errorCategory': error_category,
        'errorType': error_details['errorType'],
        'errorClass': error_details['errorClass'],
        'errorMessage': error_details['errorMessage'],
        'rootCause': root_cause,
        'matchedPattern': matched,
    }

    # Pre-existing check
    if is_pre_existing(pre_output, breaking_output):
        tprint(f"  → PRE_EXISTING (same failure in both images)")
        add_test_failure_section(json_path, {
            'status': 'PRE_EXISTING',
            'note': 'Same failure present in both pre-commit and breaking images',
            **base_info,
        }, force=force)
        return 'PRE_EXISTING'

    # Exclusion check
    excluded, exclude_pattern = is_excluded(breaking_output)
    if excluded:
        tprint(f"  → EXCLUDED ({exclude_pattern})")
        add_test_failure_section(json_path, {
            'status': 'EXCLUDED',
            'note': f'Binary incompatibility or infrastructure noise: {exclude_pattern}',
            **base_info,
        }, force=force)
        return 'EXCLUDED'

    # BBC candidate
    status = 'BBC_CANDIDATE' if failure_type != 'UNKNOWN' else 'UNKNOWN'
    add_test_failure_section(json_path, {
        'status': status,
        **base_info,
    }, force=force)

    tprint(f"  → {status} | {failure_type} / {error_category} / {error_details['errorType']}")
    return status


def main():
    workspace_root = Path(__file__).parent.parent
    benchmark_dir = workspace_root / 'data' / 'benchmark_test_failures_merged'
    batch_size = 3
    force = '--force' in sys.argv

    # Strip --force before parsing positional args
    args = [a for a in sys.argv[1:] if a != '--force']

    if len(args) > 0:
        benchmark_dir = Path(args[0])
    if len(args) > 1:
        try:
            batch_size = int(args[1])
        except ValueError:
            print("Usage: python3 analyze_failures.py [directory] [workers] [--force]")
            sys.exit(1)

    if not benchmark_dir.exists():
        print(f"Error: Directory not found: {benchmark_dir}")
        sys.exit(1)

    # json_files = sorted(benchmark_dir.glob('*.json'))
    json_files = [workspace_root / 'data' / 'benchmark_test_failures_merged' / 'f557d31b4faf102b5d2f67d86a1a4f67c09b5837.json']
    total = len(json_files)

    if total == 0:
        print(f"No JSON files found in {benchmark_dir}")
        sys.exit(1)

    print(f"Found {total} files to process")
    print(f"Batch size: {batch_size} parallel workers")
    print(f"Directory: {benchmark_dir}")
    print(f"Force overwrite: {force}\n")

    status_counts: Dict[str, list] = {
        'BBC_CANDIDATE': [],
        'PRE_EXISTING': [],
        'EXCLUDED': [],
        'SKIPPED': [],
        'UNKNOWN': [],
        'ERROR': [],
    }
    counts_lock = threading.Lock()

    def process(args):
        json_file, idx = args
        status = analyze_file(json_file, idx, total, force=force)
        with counts_lock:
            status_counts.setdefault(status, []).append(json_file.name)
        return status

    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {
            executor.submit(process, (json_file, idx)): json_file
            for idx, json_file in enumerate(json_files, 1)
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                json_file = futures[future]
                tprint(f"  ✗ Unhandled error on {json_file.name}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total files:        {total}")
    for status, files in sorted(
        status_counts.items(), key=lambda x: len(x[1]), reverse=True
    ):
        if files:
            print(f"  {status:<20} {len(files)}")

    bbc = status_counts.get('BBC_CANDIDATE', [])
    if bbc:
        print(f"\nBBC CANDIDATES ({len(bbc)}):")
        for name in bbc:
            print(f"  - {name}")


if __name__ == '__main__':
    main()