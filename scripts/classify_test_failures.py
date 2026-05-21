#!/usr/bin/env python3
"""
Script to classify benchmark test failures by their manifestation type.
Specifically identifies Test Assertion failures (BBC: Core Definition).
"""

import json
import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Define failure patterns to detect different BBC manifestation types
FAILURE_PATTERNS = {
    'TEST_ASSERTION': [
        r'AssertionError',
        r'(expected|Expected).*but (was|was:)',
        r'junit\.framework\.AssertionFailedError',
        r'org\.junit\.ComparisonFailure',
        r'Assert\.(assertEquals|assertTrue|assertFalse|assertNull|assertNotNull)',
    ],
    'PROGRAM_ASSERTION': [
        r'assert\s+',
        r'AssertionError:\s+',
    ],
    'RUNTIME_EXCEPTION': [
        r'java\.lang\.(Null|Illegal|Index|Arithmetic|Class|ArrayIndexOutOfBounds).*Exception',
        r'NullPointerException',
        r'IllegalStateException',
        r'IllegalArgumentException',
        r'ArrayIndexOutOfBoundsException',
        r'ClassCastException',
        r'NumberFormatException',
    ],
    'CHECKED_EXCEPTION': [
        r'java\.io\.IOException',
        r'java\.sql\.SQLException',
        r'java\.lang\.Exception\s+\(',
        r'Exception in thread',
    ],
    'ERROR': [
        r'java\.lang\.(Service|Verify|LinkageError|ExceptionInInitializer)',
        r'ServiceConfigurationError',
        r'VerifyError',
        r'LinkageError',
        r'Error:',
    ],
    'RESOURCE_ERROR': [
        r'(timeout|Timeout|TIMEOUT)',
        r'OutOfMemoryError',
        r'StackOverflowError',
    ],
}

class TestFailureClassifier:
    def __init__(self, benchmark_dir: str, output_file: str = None, batch_size: int = 5):
        self.benchmark_dir = Path(benchmark_dir)
        self.output_file = output_file or Path(benchmark_dir).parent / 'failure_classifications.json'
        self.results = []
        self.batch_size = batch_size
        self.lock = threading.Lock()  # For thread-safe list updates
        
    def run(self):
        """Main execution flow with parallel batch processing"""
        print(f"Starting classification of test failures (PARALLEL MODE)...")
        print(f"Input directory: {self.benchmark_dir}")
        print(f"Output file: {self.output_file}")
        print(f"Batch size (parallel workers): {self.batch_size}\n")
        
        # Get all JSON files
        json_files = sorted(self.benchmark_dir.glob('*.json'))
        total = len(json_files)
        
        if total == 0:
            print(f"No JSON files found in {self.benchmark_dir}")
            return
            
        print(f"Found {total} benchmark test failure files\n")
        
        # Process files in parallel batches
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            futures = {executor.submit(self.process_file_with_progress, json_file, idx, total): json_file 
                      for idx, json_file in enumerate(json_files, 1)}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    with self.lock:
                        self.results.append(result)
                except Exception as e:
                    json_file = futures[future]
                    print(f"✗ ERROR processing {json_file.name}: {str(e)}")
                    with self.lock:
                        self.results.append({
                            'file': json_file.name,
                            'commit': 'UNKNOWN',
                            'classification': 'ERROR',
                            'error': str(e),
                            'docker_output': '',
                        })
        
        print()  # New line after progress
        # Save results
        self.save_results()
        self.print_summary()
    
    def process_file_with_progress(self, json_file: Path, idx: int, total: int) -> Dict:
        """Process file and print progress"""
        print(f"[{idx}/{total}] {json_file.name}...", end=" ", flush=True)
        result = self.process_file(json_file)
        print(f"✓ {result['classification']}", flush=True)
        return result
        
    def process_file(self, json_file: Path) -> Dict:
        """Process a single benchmark test failure file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        commit = data.get('breakingCommit', 'UNKNOWN')
        docker_cmd = data.get('breakingUpdateReproductionCommand', '')
        
        if not docker_cmd:
            return {
                'file': json_file.name,
                'commit': commit,
                'classification': 'UNKNOWN',
                'reason': 'No breakingUpdateReproductionCommand found',
                'docker_output': '',
            }
        
        # Run Docker command and capture output
        try:
            output = self.run_docker_command(docker_cmd)
        except subprocess.TimeoutExpired:
            return {
                'file': json_file.name,
                'commit': commit,
                'classification': 'RESOURCE_ERROR',
                'reason': 'Docker command timed out',
                'docker_output': '',
            }
        except Exception as e:
            return {
                'file': json_file.name,
                'commit': commit,
                'classification': 'ERROR',
                'reason': f'Failed to run Docker: {str(e)}',
                'docker_output': '',
            }
        
        # Classify the output
        classification, matched_patterns = self.classify_output(output)
        
        return {
            'file': json_file.name,
            'commit': commit,
            'project': data.get('project', 'UNKNOWN'),
            'dependency': f"{data.get('updatedDependency', {}).get('dependencyGroupID', '')}/{data.get('updatedDependency', {}).get('dependencyArtifactID', '')}",
            'versionUpdate': f"{data.get('updatedDependency', {}).get('previousVersion', '')} → {data.get('updatedDependency', {}).get('newVersion', '')}",
            'classification': classification,
            'matched_patterns': matched_patterns,
            'docker_output_snippet': output[:500] if output else '',  # First 500 chars
        }
    
    def run_docker_command(self, docker_cmd: str, timeout: int = 600) -> str:
        """Execute Docker command and return output"""
        print(f"\n  Running: {docker_cmd[:80]}...")
        result = subprocess.run(
            docker_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Combine stdout and stderr
        output = result.stdout + result.stderr
        return output
    
    def classify_output(self, output: str) -> Tuple[str, List[str]]:
        """Classify failure based on output patterns"""
        matched = []
        
        # Check patterns in order of priority (most specific first)
        for failure_type, patterns in FAILURE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE | re.MULTILINE):
                    matched.append(pattern)
                    return failure_type, matched
        
        # Default classification if no patterns matched but there's an error
        if 'FAILED' in output or 'Error' in output or 'Exception' in output:
            return 'UNKNOWN_FAILURE', matched
        
        if not output or 'passed' in output.lower():
            return 'NO_FAILURE', matched
            
        return 'UNABLE_TO_CLASSIFY', matched
    
    def save_results(self):
        """Save results to JSON file"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_analyzed': len(self.results),
            'classifications': self._count_by_type(),
            'results': self.results
        }
        
        with open(self.output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\nResults saved to: {self.output_file}")
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count failures by classification type"""
        counts = {}
        for result in self.results:
            classification = result.get('classification', 'UNKNOWN')
            counts[classification] = counts.get(classification, 0) + 1
        return counts
    
    def print_summary(self):
        """Print summary statistics"""
        print("\n" + "="*60)
        print("CLASSIFICATION SUMMARY")
        print("="*60)
        
        counts = self._count_by_type()
        total = len(self.results)
        
        # Sort by count (descending)
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        for classification, count in sorted_counts:
            percentage = (count / total * 100) if total > 0 else 0
            print(f"{classification:.<40} {count:>4} ({percentage:>5.1f}%)")
        
        print("="*60)
        
        # Highlight TEST_ASSERTION results
        test_assertions = [r for r in self.results if r.get('classification') == 'TEST_ASSERTION']
        if test_assertions:
            print(f"\n✓ Found {len(test_assertions)} TEST ASSERTION failures (BBC: Core Definition)")
            print("\nThese are cases where the library change breaks expected behavior:")
            for result in test_assertions[:5]:  # Show first 5
                print(f"  - {result['file']}: {result['project']}")
            if len(test_assertions) > 5:
                print(f"  ... and {len(test_assertions) - 5} more")


def main():
    # Configuration
    workspace_root = Path(__file__).parent.parent
    benchmark_dir = workspace_root / 'data' / 'benchmark_test_failures'
    output_file = workspace_root / 'RQData' / 'failure_classifications.json'
    
    # Get batch size from command line, default to 5 parallel workers
    batch_size = 5
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python3 classify_test_failures.py [batch_size]")
            print(f"Example: python3 classify_test_failures.py 8")
            sys.exit(1)
    
    # Validate directory
    if not benchmark_dir.exists():
        print(f"Error: Benchmark directory not found: {benchmark_dir}")
        sys.exit(1)
    
    # Run classifier
    classifier = TestFailureClassifier(str(benchmark_dir), str(output_file), batch_size=batch_size)
    classifier.run()


if __name__ == '__main__':
    main()
