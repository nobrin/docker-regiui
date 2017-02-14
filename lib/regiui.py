# -*- coding: utf-8 -*-
# Project: docker-regiui
# Module:  regiui
import urllib2
import json
from datetime import datetime

__author__  = "Nobuo Okazaki"
__version__ = "0.2.1"
__licence__ = "MIT"

class DockerAPI(object):
    def __init__(self, urlbase):
        self.urlbase = urlbase.rstrip("/") + "/v2"

    def call(self, method, url, headers={}, data=None):
        req = urllib2.Request("%s/%s" % (self.urlbase, url), data=data)
        for n, v in headers.items(): req.add_header(n, v)
        req.get_method = lambda: method
        res = urllib2.urlopen(req)
        return res

    def version_check(self):
        self.call("GET", "")

class Registry(object):
    def __init__(self, urlbase):
        self.api = DockerAPI(urlbase)
        self.api.version_check()

    def get_reponames(self):
        res = self.api.call("GET", "_catalog")
        return sorted(json.load(res)["repositories"])

    def repo(self, reponame):
        return Repository(self.api, reponame)

    def get_images(self, content_digest):
        tags = []
        for reponame in self.get_reponames():
            repo = self.repo(reponame)
            for tagname in repo.get_tags():
                digest, manifest = repo.get_manifest(tagname)
                if digest == content_digest:
                    tags.append((reponame, tagname))
        return tags

    def delete_repo(self, reponame):
        # Delete specified repository
        repo = self.repo(reponame)
        for tag in repo.get_tags():
            repo.delete_tag(tag)
        return True

class Repository(object):
    def __init__(self, docker_api, reponame):
        self.api = docker_api
        self.name = reponame

    def get_tags(self):
        # Get tag names from registry
        res = self.api.call("GET", "%s/tags/list" % self.name)
        tags = json.load(res)["tags"] or []
        return sorted(tags)

    def get_tags_by_digest(self, content_digest):
        # Get tag names which references specified content-digest.
        tags = set()
        for tagname in self.get_tags():
            digest, manifest = self.get_manifest(tagname)
            if digest == content_digest:
                tags.add(tagname)
        return tags

    def get_manifest(self, tagname):
        res = self.api.call("GET", "%s/manifests/%s" % (self.name, tagname), headers={
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        })
        manifest_txt = res.read()
        digest = res.headers["Docker-Content-Digest"]
        return digest, manifest_txt

    def get_layer_digests(self, tagname):
        digest, manifest_txt = self.get_manifest(tagname)
        manifest = json.loads(manifest_txt)
        for layer in manifest["layers"]:
            yield layer["digest"]

    def delete_layer(self, digest):
        return self.api.call("DELETE", "%s/blobs/%s" % (self.name, digest))

    def get_info(self, tagname):
        digest, manifest_txt = self.get_manifest(tagname)
        manifest = json.loads(manifest_txt)

        # sum compressed size
        sz = 0
        for layer in manifest["layers"]: sz += layer["size"]

        config_digest = manifest["config"]["digest"]
        res = self.api.call("GET", "%s/blobs/%s" % (self.name, config_digest))
        config = json.load(res)

        # timestamp
        dts = config["created"]
        created = datetime.strptime(dts.split(".", 1)[0], "%Y-%m-%dT%H:%M:%S")

        return {
            "name":             tagname,
            "image_id":         manifest["config"]["digest"].split(":", 1)[1][:12],
            "os":               config["os"],
            "arch":             config["architecture"],
            "docker_version":   config["docker_version"],
            "author":           config.get("author", ""),
            "compressed_size":  sz,
            "created":          created,
            "labels":           config["container_config"]["Labels"],
        }

    def delete_manifest(self, digest):
        self.api.call("DELETE", "%s/manifests/%s" % (self.name, digest))
        return True

    def put_manifest(self, tagname, manifest):
        res = self.api.call("PUT", "%s/manifests/%s" % (self.name, tagname), data=manifest, headers={
            "Content-Type": "application/vnd.docker.distribution.manifest.v2+json",
        })
        return res.headers["Docker-Content-Digest"]

    def get_all_layer_digests(self, except_tag):
        # collect layer digests in this repository
        for tagname in self.get_tags():
            if tagname == except_tag: continue
            for layer_digest in self.get_layer_digests(tagname):
                yield layer_digest

    def delete_tag(self, tagname, delete_layers=False):
        # EXPERIMENTAL
        # Link the manifest to tags after deletion manifest from the specified tag.
        layers_to_delete = set()
        manifest_digest, manifest_txt = self.get_manifest(tagname)
        for layer_digest in self.get_layer_digests(tagname):
            layers_to_delete.add(layer_digest)

        # Remote used layers
        for layer_digest in self.get_all_layer_digests(except_tag=tagname):
            if layer_digest in layers_to_delete:
                layers_to_delete.remove(layer_digest)

        preserve_tags = self.get_tags_by_digest(manifest_digest)
        preserve_tags.remove(tagname)

        # Delete manifest by digest
        self.delete_manifest(manifest_digest)

        # Delete layers from this repo
        # In future, uploading same layers after deleting layers(or GC'ed) needs uploading data.
        # Without deleting, it will not need upload same layer.
        if delete_layers:
            for layer_digest in layers_to_delete:
                self.delete_layer(layer_digest)

        # Re-generate tags
        for tagname in preserve_tags:
            new_digest = self.put_manifest(tagname, manifest_txt)
            assert new_digest == manifest_digest

        return True

# --- Web application for bottle.py
def _moduleproperty(func): return type("_C", (), {"prop": property(lambda self: func())})().prop

@_moduleproperty
def app():
    import sys, os, re
    import bottle
    from bottle import Bottle, static_file, redirect, request, HTTPError

    LIB_PATH = re.sub(r"/python%d\.%d/site-packages$", "", os.path.abspath(os.path.dirname(__file__)))
    SHARE_PATH = os.path.abspath(os.path.join(LIB_PATH, "..", "share", "regiui"))
    STATIC_PATH = os.path.join(SHARE_PATH, "static")
    bottle.TEMPLATE_PATH = [os.path.join(SHARE_PATH, "views")]

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

    _app = Bottle()
    @_app.route("/")
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

    @_app.route("/test")
    def callback():
        redirect("/souffle")

    if DELETE_ENABLED:
        @_app.route("/tag-delete")
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

        @_app.route("/repo-delete")
        def callback():
            # Delete repository
            reponame = request.params.get("n")
            reg = Registry(REGISTRY)
            if reg.delete_repo(reponame):
                redirect("/")
            return "ERR"

    @_app.route("/<path:path>")
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

    return _app