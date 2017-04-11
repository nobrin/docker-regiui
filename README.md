# Docker RegiUI (Docker Registry WebUI)
Browse and delete with simple web UI for Docker registry(v2) in Python.

## Important!!
The current version has NOT be tested very well, so this is development version.  
Browsing repositries may be OK, but deleting repositries/tags might have SEVERE bugs.  If you use the feature of delete, the author does NOT recommend for critical use.  **Please use the feature at your own risk**.

## Features
The current version of RegiUI provides a basic features below:

- Browsing Docker private registry
  - Repositories
  - Tags
- Deleting repositories/tags with Registry APIv2
- Description for each repository (NEW in 0.3)
- No authentication
- No SSL

## Use with Docker(recommend)
RegiUI is prepared into Docker image.  You can run simply.

```
$ docker run -d -p 8000:8000 nobrin/docker-regiui
```

And you can access http://localhost:8000/ with your browser.
In this case, Docker Registry must listen on http://localhost:5000.

### Configuration
You can configure RegiUI with environment variables.

- REGIUI_REGISTRY -- Registry(v2) address (default: http://localhost:5000)
- REGIUI_HREF_PREFIX -- If you want to use with reverse proxy, you can set prefix. This value will be settle before links in HTML. (default: /)
- REGIUI_DELETE_ENABLED -- Turn on feature of deleting repos/tags. You must use with Registry which has been started with [REGISTRY_STORAGE_DELETE_ENABLED=true](https://github.com/docker/distribution/issues/1326). (default: false)
- REGIUI_DATA_PATH -- Path to store descriptions(default: $HOME/.local/share/regiui)

### Example configuration

First, start your Docker registry.

```
$ docker run -d --restart always --name registry \
    -v <path to data>:/var/lib/registry \
    -e REGISTRY_STORE_DELETE_ENABLED=true \
    registry:2
```

After that, start RegiUI with linking to registry.

```
$ docker run -d -p 8000:8000 --name registry-webui \
    --link registry
    -v <path to regiui data>:/var/lib/regiui \
    -e REGIUI_REGISTRY=http://registry:5000 \
    -e REGIUI_DELETE_ENABLED=true \
    nobrin/docker-regiui
```

In this configuration, RegiUI access to your Docker registry through network link on Docker.

#### Use with proxy

```
$ docker run -d -p 8000:8000 \
  --name registry-webui \
  --env REGIUI_REGISTRY=http://docker-intra.example.com:5000 \
  --env REGIUI_DELETE_ENABLED=true \
  --env REGIUI_HREF_PREFIX=/regiui \
  nobrin/docker-regiui
```

This configuration is for...

- Docker private registry is http://docker-intra.example.com:5000
- The feature of deleting is ENABLED
- URL prefix is set to /regiui (see Reverse proxy section)

## Run on real host
RegiUI requires python 2.7 and [bottle.py](https://bottlepy.org). You have to install them if they have not installed.

### CentOS 7
```
$ sudo yum -y install python2-bottle
$ export PYTHONPATH=<path to lib of RegiUI>:$PYTHONPATH
$ python /usr/lib/python2.7/site-packages/bottle.py regiui:app
Bottle v0.12.9 server starting up (using WSGIRefServer())...
Listening on http://localhost:8080/
Hit Ctrl-C to quit.
```

Now, http://localhost:8080/ is RegiUI address.

Checking options for bottle.py is:
```
$ python /usr/lib/python2.7/site-packages/bottle.py
```

## Use with reverse proxy
You can use reverse proxy. It is an example for Apache 2.2/2.4. (Sorry, the author is not familier with nginx...)

```
ProxyAddHeaders   Off  # from 2.4
ProxyAddHeaders   Off
ProxyPreserveHost Off
ProxyPass        /regiui/ http://192.168.1.1:8000/
proxyPassReverse /regiui/ http://192.168.1.1:8000/
```

## Note: Delete repos/tags with Registry APIv2
The RegiUI is delete tag below way.

1. Get digest of tag
1. Get tags whose digest is identical with the digest
1. Delete manifest identified by the digest
1. Put manifest to the preserved tags

'Put manifest' process will not change the digest.  
In APIv2, method for deleting repogitory has been found in documentation.  
**RegiUI lists repositories which have tags. Repositories without tag will be shown in index page.  But metadata directories of repositories will still remain in the registry data path.**

### Garbage collection
From [Docker documentation](https://docs.docker.com/registry/garbage-collection/):
> Registry data can occupy considerable amounts of disk space and freeing up this disk space is an oft-requested feature. Additionally for reasons of security it can be desirable to ensure that certain layers no longer exist on the filesystem.

If you want to tidy your registry data:
```
$ docker run --rm \
    -v <your registry data path>:/var/lib/registry \
    --entrypoint bin/registry \
    registry:2 \
    garbage-collect /etc/docker/registry/config.yml
```

----
## Release Notes
### 0.4.0 - 11 Apr 2017
- Add browsing namespaces

### 0.3.0 - 16 Feb 2017
- Add description editor for repositories
- Refactoring codes

### 0.2.1 - 15 Feb 2017
- Merge regiui/__init__.py and app.py

### 0.2.0 - 14 Feb 2017
- Rearrange file locations

### 0.1.0 - 13 Feb 2017
- Initial release
