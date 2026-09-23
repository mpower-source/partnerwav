#!/usr/bin/env python3
"""
Fix curly quotes in HTML/JavaScript files
Usage: python3 fix_quotes.py <filename>
"""
import sys

def fix_quotes(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_length = len(content)
        
        # Count instances before fixing
        counts_before = {
            'left_double': content.count('“'),
            'right_double': content.count('”'),
            'left_single': content.count('‘'),
            'right_single': content.count('’'),
            'em_dash': content.count('—'),
        }
        
        # Replace curly quotes with straight quotes
        replacements = [
            ('“', '"'),  # left double quote
            ('”', '"'),  # right double quote
            ('‘', "'"),  # left single quote
            ('’', "'"),  # right single quote
            ('—', '-'),  # em dash to hyphen
        ]
        
        for curly, straight in replacements:
            content = content.replace(curly, straight)
        
        # Write fixed content
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Report
        total_fixed = sum(counts_before.values())
        print(f"✓ Fixed {total_fixed} curly characters in {filename}")
        for char_type, count in counts_before.items():
            if count > 0:
                print(f"  - {char_type}: {count}")
        
        # Verify
        with open(filename, 'r', encoding='utf-8') as f:
            verify_content = f.read()
        
        if any(c in verify_content for c in '“”‘’—'):
            print("⚠ WARNING: Some curly quotes remain after fix")
            return False
        else:
            print("✓ Verification passed - file is clean!")
            return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 fix_quotes.py <filename>")
        sys.exit(1)
    
    filename = sys.argv[1]
    success = fix_quotes(filename)
    sys.exit(0 if success else 1)
