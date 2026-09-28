import os
import re

dir_path = 'd:\\SHUBHAM BACKUP\\BACKUP FOLDER\\Modern MCA Notes\\FINAL YEAR\\SEMESTER 3\\Workshop Project\\templates'
for filename in os.listdir(dir_path):
    if not filename.endswith('.html'):
        continue
    filepath = os.path.join(dir_path, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace url(#...) with currentColor
    content = re.sub(r'stroke=\"url\(#.*?\)|\'url\(#.*?\)\"', 'stroke=\"currentColor\"', content)
    # Remove <defs> blocks
    content = re.sub(r'<defs>.*?<\/defs>', '', content, flags=re.DOTALL)
    # Fix gradient-text
    content = content.replace('gradient-text', 'brand-text')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
