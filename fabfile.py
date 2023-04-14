from fabric.api import *
import fabric.contrib.project as project
import os
import stat
import re
import sys
import datetime
from bs4 import BeautifulSoup
import requests
import json
import time
from pprint import pformat

from pelicanconf import (
    ARTICLE_PATHS, DEFAULT_CATEGORY, AUTHOR, OUTPUT_PATH, THEME, THEME_BRANCH,
    PLUGIN_PATHS, PLUGIN_BRANCH, GITHUB_USER, MENUITEMS
)

# Local path configuration (can be absolute or relative to fabfile)
env.deploy_path = 'output'
DEPLOY_PATH = env.deploy_path

# Remote server configuration
production = 'root@localhost:22'
dest_path = '/var/www'

# Rackspace Cloud Files configuration settings
env.cloudfiles_username = 'my_rackspace_username'
env.cloudfiles_api_key = 'my_rackspace_api_key'
env.cloudfiles_container = 'my_cloudfiles_container'

def prebuild():
    """ tasks to run before any file generation - build, preview, publish, etc. """
    # check for themes
    if not os.path.exists(THEME):
        print(f"ERROR: theme directory {THEME} does not exist.")
        sys.exit(1)
    branch = local(
        f"cd {THEME} && git rev-parse --abbrev-ref HEAD", capture=True
    ).strip()
    if branch != THEME_BRANCH:
        print(f"ERROR: {THEME} is on wrong branch ({branch} not {THEME_BRANCH})")
        sys.exit(1)
    # check for plugins
    if not os.path.exists(os.path.join(PLUGIN_PATHS[0], 'LICENSE')):
        print(f"ERROR: plugin directory {PLUGIN_PATHS[0]} does not exist.")
        sys.exit(1)
    branch = local(
        f"cd {PLUGIN_PATHS[0]} && git rev-parse --abbrev-ref HEAD",
        capture=True,
    ).strip()
    if branch != PLUGIN_BRANCH:
        print(
            f"ERROR: {PLUGIN_PATHS[0]} is on wrong branch ({branch} not {PLUGIN_BRANCH})"
        )
        sys.exit(1)
    cats = _get_categories()
    mitems = [x[0] for x in MENUITEMS]
    if missing := [i for i in cats if i not in mitems]:
        raise RuntimeError(
            f'Categories missing from MENUITEMS in pelicanconf.py: {missing}'
        )
    update_pinned_repos()

def update_pinned_repos():
    """Update github_pinned_repos.json from user's GitHub profile"""
    fage = (
        time.time() - os.stat('github_pinned_repos.json')[stat.ST_MTIME]
        if os.path.exists('github_pinned_repos.json')
        else 999999999
    )
    if fage < 86400:
        print("GitHub Pinned Repos updated %d seconds ago; not regenerating" % fage)
        return True
    print(f"Updating GitHub Pinned Repos for user {GITHUB_USER}")
    r = requests.get(f'https://github.com/{GITHUB_USER}')
    soup = BeautifulSoup(r.text, 'html.parser')
    result = [
        {
            'name': li.select('.repo')[0].string.strip(),
            'html_url': f"https://github.com{li.select('.repo')[0].parent.attrs['href'].strip()}",
            'description': li.select('.pinned-item-desc')[0].string.strip(),
        }
        for li in soup.select('li.pinned-item-list-item')
    ]
    res = json.dumps(result)
    resp = prompt("New pinned repos:\n%s\nIs this right? [yes|No]" % pformat(result))
    if not re.match(r'(y|Y|yes|Yes|YES)', resp):
        return False
    with open('github_pinned_repos.json', 'w') as fh:
        fh.write(res)

def clean():
    """ remove DEPLOY_PATH if it exists, then recreate """
    if os.path.isdir(DEPLOY_PATH):
        local('rm -rf {deploy_path}'.format(**env))
        local('mkdir {deploy_path}'.format(**env))

def build():
    """ run pelican to build output """
    prebuild()
    local('pelican -s pelicanconf.py')

def rebuild():
    """ clean and build """
    clean()
    build()

def regenerate():
    """ pelican -r ; regenerate whenever a file changes """
    prebuild()
    local('pelican -r -s pelicanconf.py')

def serve():
    """ SimpleHTTPServer """
    local('cd {deploy_path} && python -m SimpleHTTPServer'.format(**env))

def reserve():
    """ build and serve """
    build()
    serve()

def preview():
    """ pelican with publishconf.py """
    prebuild()
    local('pelican -s publishconf.py')

def publish():
    """ rebuild and publish to GH pages """
    resp = prompt("This will clean, build, and push to GH pages. Ok? [yes|No]")
    if not re.match(r'(y|Y|yes|Yes|YES)', resp):
        return False
    clean()
    preview()
    local(f"ghp-import {OUTPUT_PATH}")
    local("git push origin gh-pages")

def _make_slug(title):
    """ make a slug from the given title """
    slug = title.lower()
    slug = re.sub('\s+', '-', slug)
    slug = re.sub(r'[^A-Za-z0-9_-]', '', slug)
    return slug

def _prompt_title():
    """ prompt for a post title """
    confirm = 'no'
    while not re.match(r'(y|Y|yes|Yes|YES)', confirm):
        title = prompt("Post Title:")
        print("")
        print(f"Post Title: '{title}'")
        print(f"Slug: '{_make_slug(title)}'")
        print("")
        confirm = prompt("Is this correct? [y|N]", default='no')
    return title

def drafts():
    """ list drafts """
    local('grep -rl -e "^Status: draft" -e "^:status: draft" content/ | grep -v "~$"')

def _prompt_category(cats):
    """ prompt for a category selection """
    print("\n\nSelect a Category:\n==================")
    for c in xrange(0, len(cats)):
        print("%d) %s" % (c, cats[c]))
    print("")
    confirm = 'no'
    while not re.match(r'(y|Y|yes|Yes|YES)', confirm):
        category = prompt("Category (number or free text):")
        print("")
        if re.match(r'[0-9]+', category):
            foo = int(category)
            if foo in xrange(0, len(cats)):
                category = cats[foo]
            else:
                print("Invalid number.")
                continue
        print(f"Category: '{category}'")
        print("")
        confirm = prompt("Is this correct? [y|N]", default='no')
    return category

def post():
    """ write a post """
    cats = _get_categories()
    title = _prompt_title()
    category = _prompt_category(cats)
    dt = datetime.datetime.now()
    dname = os.path.join(ARTICLE_PATHS[0], dt.strftime('%Y'), dt.strftime('%m'))
    if not os.path.exists(dname):
        os.makedirs(dname)
    slug = _make_slug(title)
    fname = f"{slug}.md"
    fpath = os.path.join(dname, fname)
    datestr = dt.strftime('%Y-%m-%d %H:%M')
    metadata = """Title: {title}
Date: {datestr}
Modified: {datestr}
Author: {author}
Category: {category}
Tags:
Slug: {slug}
Summary: <<<<< summary goes here >>>>>>>
Status: draft

<!--- remove this next line to disable Table of Contents -->
[TOC]
""".format(title=title,
           datestr=datestr,
           category=category,
           slug=slug,
           author=AUTHOR)
    with open(fpath, 'w') as fh:
        fh.write(metadata)
        # need to flush and fsync before an exec
        fh.flush()
        os.fsync(fh.fileno())
    if os.environ.get('EDITOR') is None:
        print(f"EDITOR not defined. Your post is started at: {fpath}")
    else:
        editor = os.environ.get('EDITOR')
        print(f"Replacing fab process with: {editor} {os.path.abspath(fpath)}")
        # replace our process with the editor...
        os.execlp(editor, os.path.basename(editor), os.path.abspath(fpath))

def _get_categories():
    """ return a list of all categories in current posts """
    lines = local(
        f'grep -rh "^Category: " {ARTICLE_PATHS[0]}/ | sort | uniq',
        capture=True,
    )
    cats = []
    cat_re = re.compile(r'^Category: (.+)$')
    for l in str(lines).split("\n"):
        if m := cat_re.match(l):
            cats.append(m[1])
    return cats

def categories():
    """ show all current blog post categories """
    for c in _get_categories():
        print c
