#!/usr/bin/env python
"""
Script to fix hilighted code blocks from WordPress wp-syntax plugin.

WordPress wp-syntax plugin (http://wordpress.org/extend/plugins/wp-syntax/)
uses a "lang" attr on pre tags to define the syntax hilighting, like:

    <pre lang="bash">
    something="foo"
    </pre>

When pelican-import runs this through Pandoc to produce MarkDown, it comes out
as a weird and meaningless block like:

    ~~~~ {lang="bash"}
    something="foo"
    ~~~~

This script takes file path(s) as arguments, and converts this junk
into proper MarkDown notation. It CHANGES FILES IN-PLACE.

REQUIREMENTS:

"""


import os
import sys
import re

from pygments import lexers

files = sys.argv[1:]

"""
translation of GeSHi identifiers to Pygments identifiers,
for GeSHi identifiers not supported by Pygments
"""
overrides = {
    'none': 'text',
    'lisp': 'common-lisp',
    'html4strict': 'html',
    'xorg': 'text',
    'nagios': 'text',
}
"""
Mapping of WP categories to new blog categories, for any that change.
"""
categories = {
    'android': 'Miscellaneous',
    'EMS, Non-Technical Commentary': 'Miscellaneous',
    'EMS, Personal': 'Miscellaneous',
    'EMS, Projects': 'Miscellaneous',
    'Higher Education': 'Miscellaneous',
    'Higher Education, Ideas and Rants': 'Miscellaneous',
    'History': 'Miscellaneous',
    'Ideas and Rants': 'Ideas and Rants',
    'Ideas and Rants, Miscellaneous Geek Stuff, Non-Technical Commentary': 'Miscellaneous',
    'Ideas and Rants, Projects, Reviews': 'Ideas and Rants',
    'Interesting Links and Resources': 'Miscellaneous',
    'Interesting Links and Resources, SysAdmin': 'Miscellaneous',
    'Miscellaneous Geek Stuff': 'Miscellaneous',
    'Miscellaneous Geek Stuff, SysAdmin': 'SysAdmin',
    'Miscellaneous Geek Stuff, Uncategorized': 'Miscellaneous',
    'Non-Technical Commentary': 'Miscellaneous',
    'opensource': 'Miscellaneous',
    'Personal': 'Miscellaneous',
    'Personal, Projects': 'Projects',
    'PHP EMS Tools': 'Projects',
    'PHPsa, Projects': 'Projects',
    'Projects': 'Projects',
    'Projects, Reviews': 'Projects',
    'Projects, Reviews, Uncategorized': 'Projects',
    'Projects, SysAdmin, Uncategorized': 'Projects',
    'Projects, Tech HowTos': 'Tech HowTos',
    'Puppet': 'Puppet',
    'Puppet, SysAdmin': 'Puppet',
    'SysAdmin, Tech HowTos': 'Tech HowTos',
    'SysAdmin, Uncategorized': 'SysAdmin',
    'Tech News': 'Miscellaneous',
    'Uncategorized': 'Miscellaneous',
    'Vehicles': 'Miscellaneous',
    'Android': 'Miscellaneous',
    'Links': 'Miscellaneous',
    'Reviews': 'Miscellaneous',
}

def translate_identifier(lexers, overrides, i, fname=None):
    """
    Translate a wp-syntax/GeSHi language identifier to
    a Pygments identifier.
    """
    if i in lexers:
        return lexers[i].lower()
    if i in overrides:
        return overrides[i]
    sys.stderr.write(f"Unknown lexer, leaving as-is: {i}")
    if fname is not None:
        sys.stderr.write(f" in file {fname}")
    sys.stderr.write("\n")
    return i

def get_lexers_list():
    """ get a list of all pygments lexers """
    d = {}
    ls = lexers.get_all_lexers()
    for l in ls:
        d[l[0]] = l[0]
        for n in l[1]:
            d[n] = l[0]
    return d

def translate_category(i):
    """ translate a category name """
    return categories[i] if i in categories else i

lang_re = re.compile(r'^~~~~ {lang="([^"]+)"}$')
cat_re = re.compile(r'^Category: (.+)$')

lexers = get_lexers_list()

for f in files:
    content = ""
    inpre = False
    count = 0
    with open(f, "r") as fh:
        for line in fh:
            m = cat_re.match(line)
            if m is not None:
                line = "Category: %s\n" % translate_category(m[1].strip())
                content = content + line
                continue
            m = lang_re.match(line)
            if m is not None:
                line = "~~~~{.%s}\n" % translate_identifier(lexers, overrides, m[1], fname=f)
                inpre = True
                count = count + 1
            elif inpre and line.strip() == "~~~~":
                inpre = False
            content = content + line
    with open(f, "w") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    print("fix_wp-syntax.py: fixed %d blocks in %s" % (count, f))
# done

