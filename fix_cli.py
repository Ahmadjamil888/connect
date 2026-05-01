import pathlib, re
content = pathlib.Path('imos_cli.py').read_text(encoding='utf-8')

# Remove ALL occurrences of the if __name__ block
pattern = r'\n\n\nif __name__ == "__main__":\n    main\(\)\n'
content = re.sub(pattern, '', content)

# Also remove any standalone if __name__ blocks
content = re.sub(r'\nif __name__ == "__main__":\n    main\(\)\n', '', content)

# Add exactly one at the end
content = content.rstrip() + '\n\n\nif __name__ == "__main__":\n    main()\n'

pathlib.Path('imos_cli.py').write_text(content, encoding='utf-8')
print('Fixed, size:', len(content))

# Verify only one main() call at end
calls = list(re.finditer(r'if __name__', content))
print('if __name__ blocks:', len(calls))
