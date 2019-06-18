from lxml import html, etree
from tkinter import filedialog
from pprint import pprint
import shutil, sys

def get_webpage_from_file():
    filename = filedialog.askopenfilename(title='HTML file to parse')
    return html.fromstring(open(filename, 'r', encoding='utf-8').read())

def get_tag(webpage):
    return webpage.tag + ': ' + ','.join(cl for cl in webpage.classes)

def build_tree(webpage):
    if webpage.getchildren() == []:
        return get_tag(webpage)
    else:
        temp = []
        for child in webpage.getchildren():
            temp.append(build_tree(child))
        return [get_tag(webpage),temp]

def tprint(tree, append):
    if isinstance(tree, str):
        print(append+tree)
    else:
        for child in tree:
            tprint(child, append+'-')

if __name__ == '__main__':
    tree = build_tree(get_webpage_from_file())
    tprint(tree, '+')
