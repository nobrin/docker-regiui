# -*- coding: utf-8 -*-
# Project:
# Module:
import sys, os
import bottle
from bottle import route, static_file, redirect, request, HTTPError
from docker_registry import Registry

bottle.TEMPLATE_PATH = [os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))]
STATIC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))

PREFIX = os.environ.get("URL_PREFIX", "/").rstrip("/") + "/"
REGISTRY = os.environ.get("REGISTRY", "http://localhost:5000")

DELETE_ENABLED = (os.environ.get("DELETE_ENABLED", "false").lower() == "true")
def template(*args, **kw):
    kw["PREFIX"] = PREFIX
    kw["DELETE_ENABLED"] = DELETE_ENABLED
    kw["size_string"] = size_string
    return bottle.template(*args, **kw)

def size_string(size):
    units = ["KiB", "MiB", "GiB", "TiB"]
    unit = "Bytes"
    while size >= 1000:
        unit = units.pop(0)
        size /= 1024.0
    return ("%.1f%s" if unit != "Bytes" else "%d%s") % (size, unit)

@route("/")
def callback():
    # List repositories
    # If a repository has no tags, it will be not shown in table.
    reg = Registry(REGISTRY)
    repos = reg.get_reponames()
    available_repos = []
    for reponame in repos:
        if not reg.repo(reponame).get_tags(): continue
        available_repos.append(reponame)
    return template("index.html", repos=available_repos)

@route("/test")
def callback():
    redirect("/souffle")

if DELETE_ENABLED:
    @route("/tag-delete")
    def callback():
        # Delete tag from repository
        fullname = request.params.get("n")
        reponame, tagname = fullname.split(":")
        reg = Registry(REGISTRY)
        repo = reg.repo(reponame)
        if repo.delete_tag(tagname):
            if repo.get_tags():
                # The repo has some tags
                redirect("/%s" % reponame)
            # The repo has no tag...
            redirect("/")

        return "ERR"

    @route("/repo-delete")
    def callback():
        # Delete repository
        reponame = request.params.get("n")
        reg = Registry(REGISTRY)
        if reg.delete_repo(reponame):
            redirect("/")
        return "ERR"

@route("/<path:path>")
def callback(path):
    reg = Registry(REGISTRY)
    repos = reg.get_reponames()

    # path is repository name
    if path in repos:
        repo = reg.repo(path)
        tagnames = repo.get_tags()
        if not tagnames:
            # repo without tag
            raise HTTPError(404, "File does not exist.")
        tags = {}
        for name in tagnames:
            tags[name] = repo.get_info(name)

        return template("repo-info.html", reponame=path, tags=tags)

    # path contains tag
    if "/" in path:
        reponame, tagname = path.rsplit("/", 1)
        if reponame in repos:
            repo = reg.repo(reponame)
            info = repo.get_info(tagname)
            return template("repo-taginfo.html", reponame=reponame, info=info)

    # return static file
    return static_file(path, root=STATIC_PATH)
