# -*- coding: utf-8 -*-
# Project:
# Module:
import urllib2
import json
from datetime import datetime

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
