"""Test encoding fix for GitCloneService"""
import tempfile
import subprocess
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.services import GitCloneService

def test_encoding_fix():
    """Test that encoding fix prevents UnicodeDecodeError"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize a git repo
        subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, capture_output=True, check=True)

        # Create a file with UTF-8 content that includes special characters
        test_file = os.path.join(temp_dir, 'test.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('Test content with UTF-8: 测试内容 🚀 特殊字符 αβγ')

        # Commit the file with UTF-8 message
        subprocess.run(['git', 'add', 'test.txt'], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit with UTF-8: 初始提交 🚀'], cwd=temp_dir, capture_output=True, check=True)

        # Test GitCloneService methods
        service = GitCloneService()

        print('Testing get_current_commit_sha...')
        try:
            sha = service.get_current_commit_sha(temp_dir)
            print(f'  Result: {sha}')
            assert sha is not None, 'Failed to get commit SHA'
            assert len(sha) == 40, f'Invalid SHA length: {len(sha)}'
            print('  ✓ Passed')
        except UnicodeDecodeError:
            print('  ✗ Failed: UnicodeDecodeError occurred!')
            sys.exit(1)

        print('Testing get_current_branch...')
        try:
            branch = service.get_current_branch(temp_dir)
            print(f'  Result: {branch}')
            assert branch is not None, 'Failed to get branch'
            print('  ✓ Passed')
        except UnicodeDecodeError:
            print('  ✗ Failed: UnicodeDecodeError occurred!')
            sys.exit(1)

        print('Testing list_files...')
        try:
            files = service.list_files(temp_dir)
            print(f'  Result: {files}')
            assert len(files) > 0, 'Failed to list files'
            assert any('test.txt' in f for f in files), 'test.txt not found in files'
            print('  ✓ Passed')
        except UnicodeDecodeError:
            print('  ✗ Failed: UnicodeDecodeError occurred!')
            sys.exit(1)

        print('\n✅ All encoding tests passed! No UnicodeDecodeError occurred.')

if __name__ == '__main__':
    test_encoding_fix()
