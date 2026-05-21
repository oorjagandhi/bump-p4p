#!/usr/bin/env python3
"""
Analysis helper - Extract and analyze TEST_ASSERTION failures
Run this after classify_test_failures.py or classify_test_failures_sample.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def analyze_classifications(json_file: Path):
    """Analyze classification results"""
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    print(f"\n{'='*70}")
    print(f"Classification Analysis: {json_file.name}")
    print(f"{'='*70}\n")
    
    results = data.get('results', [])
    classifications = data.get('classifications', {})
    
    # Print summary
    print("SUMMARY")
    print("-" * 70)
    for cls_type, count in sorted(classifications.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(results) * 100) if results else 0
        bar = "█" * int(pct / 2)
        print(f"{cls_type:.<30} {count:>4} ({pct:>5.1f}%) {bar}")
    
    print(f"\nTotal files analyzed: {data.get('total_analyzed')}")
    print(f"Timestamp: {data.get('timestamp')}")
    
    # Extract TEST_ASSERTION failures
    print(f"\n{'='*70}")
    print("TEST ASSERTION FAILURES (BBC: Core Definition)")
    print(f"{'='*70}\n")
    
    test_assertions = [r for r in results if r.get('classification') == 'TEST_ASSERTION']
    
    if not test_assertions:
        print("✗ No test assertion failures found")
    else:
        print(f"✓ Found {len(test_assertions)} test assertion failures\n")
        
        # Group by project
        by_project = defaultdict(list)
        for result in test_assertions:
            project = result.get('project', 'UNKNOWN')
            by_project[project].append(result)
        
        # Print by project
        for project in sorted(by_project.keys()):
            failures = by_project[project]
            print(f"  {project}")
            for result in failures:
                dep = result.get('dependency', 'UNKNOWN')
                ver = result.get('versionUpdate', 'UNKNOWN')
                print(f"    - {result['file']}")
                if dep != 'UNKNOWN':
                    print(f"      Dependency: {dep} ({ver})")
            print()
    
    # Other failure types summary
    print(f"\n{'='*70}")
    print("OTHER FAILURE TYPES")
    print(f"{'='*70}\n")
    
    other_types = {k: v for k, v in classifications.items() if k != 'TEST_ASSERTION'}
    for failure_type in sorted(other_types.keys(), key=lambda x: other_types[x], reverse=True):
        count = other_types[failure_type]
        matching = [r for r in results if r.get('classification') == failure_type]
        print(f"{failure_type}: {count} failures")
        for result in matching[:3]:  # Show first 3
            print(f"  - {result['file']} ({result.get('project', 'UNKNOWN')})")
        if len(matching) > 3:
            print(f"  ... and {len(matching) - 3} more")
        print()
    
    # Export options
    print(f"\n{'='*70}")
    print("EXPORT OPTIONS")
    print(f"{'='*70}\n")
    
    # Export to CSV
    csv_file = json_file.parent / f"{json_file.stem}_test_assertions.csv"
    export_to_csv(test_assertions, csv_file)
    
    # Export to text
    txt_file = json_file.parent / f"{json_file.stem}_test_assertions.txt"
    export_to_text(test_assertions, txt_file)
    
    print(f"✓ Exported test assertions to:")
    print(f"  - {csv_file.relative_to(json_file.parent.parent)}")
    print(f"  - {txt_file.relative_to(json_file.parent.parent)}")


def export_to_csv(test_assertions, csv_file: Path):
    """Export to CSV format"""
    import csv
    
    with open(csv_file, 'w', newline='') as f:
        if not test_assertions:
            return
        
        fieldnames = ['file', 'commit', 'project', 'dependency', 'versionUpdate']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in test_assertions:
            writer.writerow({
                'file': result.get('file', ''),
                'commit': result.get('commit', ''),
                'project': result.get('project', ''),
                'dependency': result.get('dependency', ''),
                'versionUpdate': result.get('versionUpdate', ''),
            })


def export_to_text(test_assertions, txt_file: Path):
    """Export to text format"""
    
    with open(txt_file, 'w') as f:
        f.write("TEST ASSERTION FAILURES (BBC: Core Definition)\n")
        f.write("="*70 + "\n\n")
        
        for i, result in enumerate(test_assertions, 1):
            f.write(f"{i}. {result.get('project', 'UNKNOWN')}\n")
            f.write(f"   File: {result.get('file', 'UNKNOWN')}\n")
            f.write(f"   Commit: {result.get('commit', 'UNKNOWN')}\n")
            f.write(f"   Dependency: {result.get('dependency', 'UNKNOWN')}\n")
            f.write(f"   Version Update: {result.get('versionUpdate', 'UNKNOWN')}\n")
            f.write("\n")


def main():
    # Find latest classification file
    workspace_root = Path(__file__).parent.parent
    rqdata_dir = workspace_root / 'RQData'
    
    # Check for classification files
    classification_files = list(rqdata_dir.glob('failure_classifications*.json'))
    
    if not classification_files:
        print("Error: No classification files found in RQData/")
        print("Run classify_test_failures.py or classify_test_failures_sample.py first")
        sys.exit(1)
    
    # Use the most recent file if multiple exist
    json_file = sorted(classification_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    
    print(f"\nUsing: {json_file.name}")
    analyze_classifications(json_file)


if __name__ == '__main__':
    main()
